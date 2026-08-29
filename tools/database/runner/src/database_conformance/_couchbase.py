# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Couchbase Community Server backend definition."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from types import TracebackType
from typing import cast

from docker.errors import DockerException
from testcontainers.core.container import DockerContainer, ExecConfig
from testcontainers.core.wait_strategies import ExecWaitStrategy

from opentelemetry.conformance._env import timeout_seconds

from ._container import DATABASE_HOST, DatabaseBackendError

COUCHBASE_DATABASE = "conformance"
COUCHBASE_SCOPE = "conformance"
COUCHBASE_COLLECTION = "items"
COUCHBASE_USER = "Administrator"
COUCHBASE_PASSWORD = "conformance-password"
COUCHBASE_MANAGEMENT_PORT = 8091
COUCHBASE_KV_PORT = 11210
# renovate: datasource=docker depName=couchbase/server versioning=regex:^community-(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)$
COUCHBASE_IMAGE = "couchbase/server:community-7.6.2@sha256:d098341bafcdacdfb47036a6f59c1b6bb9e798f3969b553c3d26cb74f48ca1fb"

_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_COUCHBASE_STARTUP_TIMEOUT", 180.0)
_POLL_INTERVAL_SECONDS = 0.5
_PortBinding = int | tuple[str, int] | None


class Couchbase:
    """Own one initialized Couchbase Community Server container."""

    def __init__(
        self,
        *,
        container_factory: Callable[[str], DockerContainer] = DockerContainer,
    ) -> None:
        self._container_factory = container_factory
        self._container: DockerContainer | None = None
        self._management_port: int | None = None
        self._kv_port: int | None = None

    @property
    def variables(self) -> Mapping[str, str]:
        if self._management_port is None or self._kv_port is None:
            raise DatabaseBackendError("Couchbase has not been started")
        return {
            "DATABASE_HOST": DATABASE_HOST,
            "DATABASE_PORT": str(self._kv_port),
            "DATABASE_NAME": COUCHBASE_DATABASE,
            "DATABASE_USER": COUCHBASE_USER,
            "DATABASE_PASSWORD": COUCHBASE_PASSWORD,
            "COUCHBASE_MANAGEMENT_PORT": str(self._management_port),
            "COUCHBASE_KV_PORT": str(self._kv_port),
            "COUCHBASE_CONNECTION_STRING": (
                f"couchbase://{DATABASE_HOST}:{self._kv_port}"
            ),
            "COUCHBASE_SCOPE": COUCHBASE_SCOPE,
            "COUCHBASE_COLLECTION": COUCHBASE_COLLECTION,
        }

    def start(self) -> Couchbase:
        if self._container is not None:
            raise DatabaseBackendError("Couchbase has already been started")

        ready = (
            ExecWaitStrategy(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "http://127.0.0.1:8091/pools",
                ]
            )
            .with_startup_timeout(
                timedelta(seconds=timeout_seconds(*_STARTUP_TIMEOUT))
            )
            .with_poll_interval(_POLL_INTERVAL_SECONDS)
        )
        container = self._container_factory(COUCHBASE_IMAGE)
        container.waiting_for(ready)
        port_bindings = cast(dict[str, _PortBinding], container.ports)
        port_bindings[f"{COUCHBASE_MANAGEMENT_PORT}/tcp"] = (DATABASE_HOST, 0)
        port_bindings[f"{COUCHBASE_KV_PORT}/tcp"] = (DATABASE_HOST, 0)

        self._container = container
        try:
            container.start()
            self._management_port = container.get_exposed_port(
                COUCHBASE_MANAGEMENT_PORT
            )
            self._kv_port = container.get_exposed_port(COUCHBASE_KV_PORT)
            self._initialize(container)
        except BaseException as error:
            try:
                self.close()
            except DockerException as cleanup_error:
                raise DatabaseBackendError(
                    f"{error}\nCouchbase cleanup also failed: {cleanup_error}"
                ) from error
            raise
        return self

    def _initialize(self, container: DockerContainer) -> None:
        self._exec(
            container,
            (
                "couchbase-cli",
                "cluster-init",
                "--cluster",
                "127.0.0.1",
                "--cluster-username",
                COUCHBASE_USER,
                "--cluster-password",
                COUCHBASE_PASSWORD,
                "--cluster-name",
                "otel-conformance",
                "--services",
                "data",
                "--cluster-ramsize",
                "512",
            ),
            "initialize the Couchbase cluster",
        )
        self._exec(
            container,
            (
                "couchbase-cli",
                "bucket-create",
                "--cluster",
                "127.0.0.1",
                "--username",
                COUCHBASE_USER,
                "--password",
                COUCHBASE_PASSWORD,
                "--bucket",
                COUCHBASE_DATABASE,
                "--bucket-type",
                "couchbase",
                "--bucket-ramsize",
                "128",
                "--bucket-replica",
                "0",
                "--wait",
            ),
            "create the Couchbase bucket",
        )
        self._exec(
            container,
            (
                "couchbase-cli",
                "collection-manage",
                "--cluster",
                "127.0.0.1",
                "--username",
                COUCHBASE_USER,
                "--password",
                COUCHBASE_PASSWORD,
                "--bucket",
                COUCHBASE_DATABASE,
                "--create-scope",
                COUCHBASE_SCOPE,
            ),
            "create the Couchbase scope",
        )
        self._exec(
            container,
            (
                "couchbase-cli",
                "collection-manage",
                "--cluster",
                "127.0.0.1",
                "--username",
                COUCHBASE_USER,
                "--password",
                COUCHBASE_PASSWORD,
                "--bucket",
                COUCHBASE_DATABASE,
                "--create-collection",
                f"{COUCHBASE_SCOPE}.{COUCHBASE_COLLECTION}",
            ),
            "create the Couchbase collection",
        )
        self._exec(
            container,
            (
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--user",
                f"{COUCHBASE_USER}:{COUCHBASE_PASSWORD}",
                "--request",
                "PUT",
                "http://127.0.0.1:8091/node/controller/setupAlternateAddresses/external",
                "--data-urlencode",
                f"hostname={DATABASE_HOST}",
                "--data",
                f"mgmt={self._management_port}",
                "--data",
                f"kv={self._kv_port}",
            ),
            "configure Couchbase external ports",
        )

    @staticmethod
    def _exec(
        container: DockerContainer,
        command: Sequence[str],
        action: str,
    ) -> None:
        result = container.exec(ExecConfig(command=list(command)))
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
            logs = f"Could not read Couchbase logs: {error}"
        raise DatabaseBackendError(
            f"Could not {action}; the command exited with "
            f"{result.exit_code}\n{output}\n--- Couchbase logs ---\n{logs}"
        )

    def close(self) -> None:
        if self._container is None:
            return
        self._container.stop()
        self._container = None
        self._management_port = None
        self._kv_port = None

    def __enter__(self) -> Couchbase:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
