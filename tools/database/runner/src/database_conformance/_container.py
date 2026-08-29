# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared Testcontainers lifecycle for database backends."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from importlib import resources
from types import TracebackType
from typing import Protocol, TypeVar, cast

from docker.errors import DockerException
from testcontainers.core.container import DockerContainer, ExecConfig
from testcontainers.core.wait_strategies import ExecWaitStrategy

from opentelemetry.conformance._env import timeout_seconds

DATABASE_HOST = "127.0.0.1"
_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT", 60.0)
_POLL_INTERVAL_SECONDS = 0.25

_PortBinding = int | tuple[str, int] | None
_DatabaseContainerT = TypeVar("_DatabaseContainerT", bound="DatabaseContainer")


class DatabaseBackendError(RuntimeError):
    """A managed database could not be started or initialized."""


class DatabaseBackend(Protocol):
    """A database lifecycle that supplies scenario variables."""

    @property
    def variables(self) -> Mapping[str, str]: ...

    def __enter__(self) -> DatabaseBackend: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True)
class BackendSpec:
    """Everything the shared container lifecycle needs for one database."""

    name: str
    image: str
    port: int
    database: str
    user: str
    password: str
    environment: tuple[tuple[str, str], ...]
    ready_command: tuple[str, ...]
    schema_resource: str
    schema_path: str
    schema_command: tuple[str, ...]
    schema_environment: tuple[tuple[str, str], ...] = ()


class DatabaseContainer:
    """Own one disposable database initialized from a packaged schema."""

    def __init__(
        self,
        spec: BackendSpec,
        *,
        container_factory: Callable[[str], DockerContainer],
    ) -> None:
        self._spec = spec
        self._container_factory = container_factory
        self._container: DockerContainer | None = None
        self._published_port: int | None = None

    @property
    def variables(self) -> Mapping[str, str]:
        if self._published_port is None:
            raise DatabaseBackendError(
                f"{self._spec.name} has not been started"
            )
        return {
            "DATABASE_HOST": DATABASE_HOST,
            "DATABASE_PORT": str(self._published_port),
            "DATABASE_NAME": self._spec.database,
            "DATABASE_USER": self._spec.user,
            "DATABASE_PASSWORD": self._spec.password,
        }

    def start(self: _DatabaseContainerT) -> _DatabaseContainerT:
        if self._container is not None:
            raise DatabaseBackendError(
                f"{self._spec.name} has already been started"
            )

        schema = (
            resources.files("database_conformance")
            .joinpath(self._spec.schema_resource)
            .read_bytes()
        )
        ready = (
            ExecWaitStrategy(list(self._spec.ready_command))
            .with_startup_timeout(
                timedelta(seconds=timeout_seconds(*_STARTUP_TIMEOUT))
            )
            .with_poll_interval(_POLL_INTERVAL_SECONDS)
        )
        container = self._container_factory(self._spec.image)
        for key, value in self._spec.environment:
            container.with_env(key, value)
        container.with_copy_into_container(schema, self._spec.schema_path)
        container.waiting_for(ready)

        port_bindings = cast(dict[str, _PortBinding], container.ports)
        port_bindings[f"{self._spec.port}/tcp"] = (DATABASE_HOST, 0)

        self._container = container
        try:
            container.start()
            self._published_port = container.get_exposed_port(self._spec.port)
            self._apply_schema(container)
        except BaseException as error:
            try:
                self.close()
            except DockerException as cleanup_error:
                raise DatabaseBackendError(
                    f"{error}\n{self._spec.name} cleanup also failed: "
                    f"{cleanup_error}"
                ) from error
            raise
        return self

    def _apply_schema(self, container: DockerContainer) -> None:
        result = container.exec(
            ExecConfig(
                command=list(self._spec.schema_command),
                environment=dict(self._spec.schema_environment),
            )
        )
        if result.exit_code == 0:
            return

        output = result.output.decode(
            encoding="utf-8", errors="replace"
        ).strip()
        try:
            stdout, stderr = container.get_logs()
            logs = (
                (stdout + stderr)
                .decode(encoding="utf-8", errors="replace")
                .strip()
            )
        except DockerException as error:
            logs = f"Could not read {self._spec.name} logs: {error}"
        raise DatabaseBackendError(
            f"Could not apply the {self._spec.name} schema; the client exited "
            f"with {result.exit_code}\n{output}\n"
            f"--- {self._spec.name} logs ---\n{logs}"
        )

    def close(self) -> None:
        if self._container is None:
            return
        self._container.stop()
        self._container = None
        self._published_port = None

    def __enter__(self: _DatabaseContainerT) -> _DatabaseContainerT:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
