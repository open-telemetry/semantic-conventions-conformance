# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A session-scoped PostgreSQL backend managed through Testcontainers."""

from __future__ import annotations

from datetime import timedelta
from importlib import resources
from types import TracebackType
from typing import Mapping, cast

from docker.errors import DockerException
from testcontainers.core.container import DockerContainer, ExecConfig
from testcontainers.core.wait_strategies import ExecWaitStrategy

from opentelemetry.conformance._env import timeout_seconds

# renovate: datasource=docker depName=postgres versioning=docker
POSTGRES_IMAGE = "postgres:18.6-bookworm@sha256:1c59e2c3c818eaa0f0628f695b36e7c9e362d6b219b36a54a32df645cbd7e1af"

POSTGRES_HOST = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_DATABASE = "conformance"
POSTGRES_USER = "conformance"
POSTGRES_PASSWORD = "conformance"

_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_POSTGRES_STARTUP_TIMEOUT", 60.0)
_POLL_INTERVAL_SECONDS = 0.25
_SCHEMA_PATH = "/tmp/otel-conformance-postgres.sql"

_PortBinding = int | tuple[str, int] | None


class Postgres:
    """Own one PostgreSQL container and its initialized schema."""

    def __init__(self) -> None:
        self._container: DockerContainer | None = None
        self._published_port: int | None = None

    @property
    def variables(self) -> Mapping[str, str]:
        """Language-neutral connection fields for scenario environments."""
        if self._published_port is None:
            raise RuntimeError("PostgreSQL has not been started")
        return {
            "POSTGRES_HOST": POSTGRES_HOST,
            "POSTGRES_PORT": str(self._published_port),
            "POSTGRES_DATABASE": POSTGRES_DATABASE,
            "POSTGRES_USER": POSTGRES_USER,
            "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        }

    def start(self) -> Postgres:
        """Start PostgreSQL, wait until it is ready, and apply the schema."""
        if self._container is not None:
            raise RuntimeError("PostgreSQL has already been started")

        schema = (
            resources.files("database_conformance")
            .joinpath("postgres.sql")
            .read_bytes()
        )
        ready = (
            ExecWaitStrategy(
                [
                    "pg_isready",
                    "--host",
                    POSTGRES_HOST,
                    "--port",
                    str(POSTGRES_PORT),
                    "--username",
                    POSTGRES_USER,
                    "--dbname",
                    POSTGRES_DATABASE,
                ]
            )
            .with_startup_timeout(
                timedelta(seconds=timeout_seconds(*_STARTUP_TIMEOUT))
            )
            .with_poll_interval(_POLL_INTERVAL_SECONDS)
        )
        container = (
            DockerContainer(POSTGRES_IMAGE)
            .with_env("POSTGRES_DB", POSTGRES_DATABASE)
            .with_env("POSTGRES_USER", POSTGRES_USER)
            .with_env("POSTGRES_PASSWORD", POSTGRES_PASSWORD)
            .with_copy_into_container(schema, _SCHEMA_PATH)
            .waiting_for(ready)
        )

        # Docker accepts (host, port) bindings, but Testcontainers narrows this
        # public mapping to integer ports.
        port_bindings = cast(dict[str, _PortBinding], container.ports)
        port_bindings[f"{POSTGRES_PORT}/tcp"] = (POSTGRES_HOST, 0)

        self._container = container
        try:
            container.start()
            self._published_port = container.get_exposed_port(POSTGRES_PORT)
            self._apply_schema(container)
        except BaseException as error:
            try:
                self.close()
            except DockerException as cleanup_error:
                raise RuntimeError(
                    f"{error}\nPostgreSQL cleanup also failed: {cleanup_error}"
                ) from error
            raise

        return self

    @staticmethod
    def _apply_schema(container: DockerContainer) -> None:
        result = container.exec(
            ExecConfig(
                command=[
                    "psql",
                    "--no-psqlrc",
                    "--set",
                    "ON_ERROR_STOP=1",
                    "--host",
                    POSTGRES_HOST,
                    "--port",
                    str(POSTGRES_PORT),
                    "--username",
                    POSTGRES_USER,
                    "--dbname",
                    POSTGRES_DATABASE,
                    "--file",
                    _SCHEMA_PATH,
                ],
                environment={"PGPASSWORD": POSTGRES_PASSWORD},
            )
        )
        if result.exit_code == 0:
            return

        output = result.output.decode(encoding="utf-8", errors="replace").strip()
        try:
            stdout, stderr = container.get_logs()
            logs = (stdout + stderr).decode(
                encoding="utf-8", errors="replace"
            ).strip()
        except DockerException as error:
            logs = f"Could not read PostgreSQL logs: {error}"
        raise RuntimeError(
            "Could not apply the PostgreSQL schema; psql exited with "
            f"{result.exit_code}\n{output}\n"
            f"--- PostgreSQL logs ---\n{logs}"
        )

    def close(self) -> None:
        """Remove PostgreSQL if it was started."""
        if self._container is None:
            return
        self._container.stop()
        self._container = None
        self._published_port = None

    def __enter__(self) -> Postgres:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
