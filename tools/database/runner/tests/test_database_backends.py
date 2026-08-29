# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Managed database container lifecycles."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

import pytest
from docker.errors import DockerException
from testcontainers.core.container import ExecConfig

from database_conformance import _mariadb, _postgres
from database_conformance._couchbase import COUCHBASE_IMAGE, Couchbase
from database_conformance._mariadb import MARIADB_IMAGE, MariaDB
from database_conformance._postgres import POSTGRES_IMAGE, Postgres


@dataclass
class ExecResult:
    exit_code: int | None = 0
    output: bytes = b""


class StubContainer:
    def __init__(
        self,
        *,
        start_error: BaseException | None = None,
        stop_error: Exception | None = None,
        exec_result: ExecResult | None = None,
        exec_results: list[ExecResult] | None = None,
        port: int = 5432,
        published_ports: dict[int, int] | None = None,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.exec_result = exec_result or ExecResult()
        self.exec_results = list(exec_results or [])
        self.port = port
        self.published_ports = published_ports or {}
        self.env: dict[str, str] = {}
        self.ports: dict[str, Any] = {}
        self.transfers: list[tuple[bytes, str]] = []
        self.wait_strategy: object | None = None
        self.exec_configs: list[ExecConfig] = []
        self.started = False
        self.stopped = False

    def with_env(self, key: str, value: str) -> StubContainer:
        self.env[key] = value
        return self

    def with_copy_into_container(
        self, source: bytes, destination: str
    ) -> StubContainer:
        self.transfers.append((source, destination))
        return self

    def waiting_for(self, strategy: object) -> StubContainer:
        self.wait_strategy = strategy
        return self

    def start(self) -> StubContainer:
        if self.start_error is not None:
            raise self.start_error
        self.started = True
        return self

    def get_exposed_port(self, port: int) -> int:
        if port in self.published_ports:
            return self.published_ports[port]
        assert port == self.port
        return 32768

    def exec(self, config: ExecConfig) -> ExecResult:
        self.exec_configs.append(config)
        if self.exec_results:
            return self.exec_results.pop(0)
        return self.exec_result

    def get_logs(self) -> tuple[bytes, bytes]:
        return b"ready to accept connections\n", b""

    def stop(self) -> None:
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error


def install_stub(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    container: StubContainer,
) -> None:
    monkeypatch.setattr(module, "DockerContainer", lambda _: container)


@pytest.mark.parametrize(
    ("module", "backend_type", "port", "expected_environment"),
    [
        (
            _postgres,
            Postgres,
            5432,
            {
                "POSTGRES_DB": "conformance",
                "POSTGRES_USER": "conformance",
                "POSTGRES_PASSWORD": "conformance",
            },
        ),
        (
            _mariadb,
            MariaDB,
            3306,
            {
                "MARIADB_DATABASE": "conformance",
                "MARIADB_USER": "conformance",
                "MARIADB_PASSWORD": "conformance",
                "MARIADB_RANDOM_ROOT_PASSWORD": "yes",
            },
        ),
    ],
)
def test_starts_initializes_publishes_and_removes_database(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: type[Postgres] | type[MariaDB],
    port: int,
    expected_environment: dict[str, str],
) -> None:
    container = StubContainer(port=port)
    install_stub(monkeypatch, module, container)

    with backend_type() as database:
        assert database.variables == {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "32768",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": "conformance",
            "DATABASE_PASSWORD": "conformance",
        }

    assert container.started
    assert container.stopped
    assert container.env == expected_environment
    assert container.ports == {f"{port}/tcp": ("127.0.0.1", 0)}
    assert container.transfers
    schema, path = container.transfers[0]
    assert path.startswith("/tmp/otel-conformance-")
    assert b"CREATE" in schema
    assert b"INSERT INTO" not in schema
    assert container.wait_strategy is not None
    assert container.exec_configs


def test_starts_initializes_publishes_and_removes_couchbase() -> None:
    container = StubContainer(
        published_ports={
            8091: 32768,
            11210: 32769,
        }
    )

    with Couchbase(container_factory=lambda _: container) as database:
        assert database.variables == {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "32769",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": "Administrator",
            "DATABASE_PASSWORD": "conformance-password",
            "COUCHBASE_MANAGEMENT_PORT": "32768",
            "COUCHBASE_KV_PORT": "32769",
            "COUCHBASE_CONNECTION_STRING": "couchbase://127.0.0.1:32769",
            "COUCHBASE_SCOPE": "conformance",
            "COUCHBASE_COLLECTION": "items",
        }

    assert container.started
    assert container.stopped
    assert container.ports == {
        "8091/tcp": ("127.0.0.1", 0),
        "11210/tcp": ("127.0.0.1", 0),
    }
    assert container.wait_strategy is not None
    commands = [config.command for config in container.exec_configs]
    assert [command[:2] for command in commands] == [
        ["couchbase-cli", "cluster-init"],
        ["couchbase-cli", "bucket-create"],
        ["couchbase-cli", "collection-manage"],
        ["couchbase-cli", "collection-manage"],
        ["curl", "--fail"],
    ]
    assert "conformance.items" in commands[3]
    assert "mgmt=32768" in commands[4]
    assert "kv=32769" in commands[4]


def test_couchbase_bootstrap_failure_reports_output_and_cleans_up() -> None:
    container = StubContainer(
        exec_results=[ExecResult(exit_code=1, output=b"cluster init failed")],
        published_ports={8091: 32768, 11210: 32769},
    )

    with pytest.raises(
        RuntimeError,
        match=r"(?s)cluster init failed.*ready to accept connections",
    ):
        Couchbase(container_factory=lambda _: container).start()

    assert container.stopped


def test_start_failure_cleans_up_the_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(start_error=RuntimeError("startup failed"))
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(RuntimeError, match="startup failed"):
        Postgres().start()

    assert container.stopped


def test_cleanup_failure_is_reported_with_start_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        start_error=RuntimeError("startup failed"),
        stop_error=DockerException("cleanup failed"),
    )
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(
        RuntimeError,
        match="startup failed\nPostgreSQL cleanup also failed: cleanup failed",
    ):
        Postgres().start()


def test_schema_failure_reports_psql_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        exec_result=ExecResult(exit_code=3, output=b"syntax error")
    )
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)syntax error.*ready to accept connections",
    ):
        Postgres().start()

    assert container.stopped


def test_cannot_start_postgres_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer()
    install_stub(monkeypatch, _postgres, container)
    postgres = Postgres().start()

    with pytest.raises(RuntimeError, match="already been started"):
        postgres.start()

    postgres.close()


def test_the_image_is_pinned_by_digest() -> None:
    name, separator, digest = COUCHBASE_IMAGE.partition("@")
    assert name == "couchbase/server:community-7.6.2"
    assert separator == "@"
    assert digest.startswith("sha256:")

    name, separator, digest = POSTGRES_IMAGE.partition("@")

    assert name == "postgres:18.6-bookworm"
    assert separator == "@"
    assert digest.startswith("sha256:")

    name, separator, digest = MARIADB_IMAGE.partition("@")
    assert name == "mariadb:11.8.9-noble"
    assert separator == "@"
    assert digest.startswith("sha256:")


def test_the_schema_is_packaged_with_the_runner() -> None:
    schema = (
        resources.files("database_conformance")
        .joinpath("postgres.sql")
        .read_text(encoding="utf-8")
    )

    assert "CREATE TABLE IF NOT EXISTS conformance.items" in schema
    assert "CREATE OR REPLACE PROCEDURE conformance.noop()" in schema

    schema = (
        resources.files("database_conformance")
        .joinpath("mariadb.sql")
        .read_text(encoding="utf-8")
    )
    assert "CREATE TABLE IF NOT EXISTS items" in schema
    assert "CREATE OR REPLACE PROCEDURE noop()" in schema
