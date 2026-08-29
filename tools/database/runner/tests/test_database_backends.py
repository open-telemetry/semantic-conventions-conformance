# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Managed database container lifecycles."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib import resources
from typing import Any

import pytest
from docker.errors import DockerException
from testcontainers.core.container import ExecConfig

from database_conformance import _cassandra, _mariadb, _postgres, _redis, _sql_server
from database_conformance._cassandra import CASSANDRA_IMAGE, Cassandra
from database_conformance._container import DatabaseContainer
from database_conformance._mariadb import MARIADB_IMAGE, MariaDB
from database_conformance._postgres import POSTGRES_IMAGE, Postgres
from database_conformance._redis import REDIS_IMAGE, Redis
from database_conformance._sql_server import SQL_SERVER_IMAGE, SQLServer


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
        port: int = 5432,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.exec_result = exec_result or ExecResult()
        self.port = port
        self.env: dict[str, str] = {}
        self.ports: dict[str, Any] = {}
        self.transfers: list[tuple[bytes, str]] = []
        self.wait_strategy: object | None = None
        self.exec_config: ExecConfig | None = None
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
        assert port == self.port
        return 32768

    def exec(self, config: ExecConfig) -> ExecResult:
        self.exec_config = config
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
    monkeypatch.setattr(module, "DockerContainer", lambda _image: container)


@pytest.mark.parametrize(
    (
        "module",
        "backend_type",
        "port",
        "expected_environment",
        "expected_variables",
        "expected_schema_paths",
        "expected_initialization",
    ),
    [
        (
            _cassandra,
            Cassandra,
            9042,
            {
                "CASSANDRA_CLUSTER_NAME": "otel-conformance",
                "CASSANDRA_DC": "datacenter1",
                "CASSANDRA_NUM_TOKENS": "1",
                "MAX_HEAP_SIZE": "256M",
                "HEAP_NEWSIZE": "64M",
            },
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "conformance",
                "DATABASE_USER": "",
                "DATABASE_PASSWORD": "",
                "DATABASE_LOCAL_DATACENTER": "datacenter1",
            },
            ["/tmp/otel-conformance-cassandra.cql"],
            ExecConfig(
                command=[
                    "cqlsh",
                    "127.0.0.1",
                    "9042",
                    "--file",
                    "/tmp/otel-conformance-cassandra.cql",
                ],
                environment={},
            ),
        ),
        (
            _postgres,
            Postgres,
            5432,
            {
                "POSTGRES_DB": "conformance",
                "POSTGRES_USER": "conformance",
                "POSTGRES_PASSWORD": "conformance",
            },
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "conformance",
                "DATABASE_USER": "conformance",
                "DATABASE_PASSWORD": "conformance",
            },
            ["/tmp/otel-conformance-postgres.sql"],
            ExecConfig(
                command=[
                    "psql",
                    "--no-psqlrc",
                    "--set",
                    "ON_ERROR_STOP=1",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5432",
                    "--username",
                    "conformance",
                    "--dbname",
                    "conformance",
                    "--file",
                    "/tmp/otel-conformance-postgres.sql",
                ],
                environment={"PGPASSWORD": "conformance"},
            ),
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
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "conformance",
                "DATABASE_USER": "conformance",
                "DATABASE_PASSWORD": "conformance",
            },
            ["/tmp/otel-conformance-mariadb.sql"],
            ExecConfig(
                command=[
                    "sh",
                    "-c",
                    "exec mariadb --user=conformance --database=conformance "
                    "--binary-mode < /tmp/otel-conformance-mariadb.sql",
                ],
                environment={"MYSQL_PWD": "conformance"},
            ),
        ),
        (
            _redis,
            Redis,
            6379,
            {},
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "0",
                "DATABASE_USER": "default",
                "DATABASE_PASSWORD": "",
            },
            [],
            None,
        ),
        (
            _sql_server,
            SQLServer,
            1433,
            {
                "ACCEPT_EULA": "Y",
                "MSSQL_PID": "Developer",
                "MSSQL_SA_PASSWORD": "Conformance1!",
            },
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "conformance",
                "DATABASE_USER": "sa",
                "DATABASE_PASSWORD": "Conformance1!",
            },
            ["/tmp/otel-conformance-sql-server.sql"],
            ExecConfig(
                command=[
                    "/opt/mssql-tools18/bin/sqlcmd",
                    "-S",
                    "127.0.0.1",
                    "-U",
                    "sa",
                    "-C",
                    "-b",
                    "-i",
                    "/tmp/otel-conformance-sql-server.sql",
                ],
                environment={"SQLCMDPASSWORD": "Conformance1!"},
            ),
        ),
    ],
)
def test_starts_initializes_publishes_and_removes_database(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: Callable[[], DatabaseContainer],
    port: int,
    expected_environment: dict[str, str],
    expected_variables: dict[str, str],
    expected_schema_paths: list[str],
    expected_initialization: ExecConfig | None,
) -> None:
    container = StubContainer(port=port)
    install_stub(monkeypatch, module, container)

    with backend_type() as database:
        assert database.variables == expected_variables

    assert container.started
    assert container.stopped
    assert container.env == expected_environment
    assert container.ports == {f"{port}/tcp": ("127.0.0.1", 0)}
    assert [path for _, path in container.transfers] == expected_schema_paths
    for schema, _ in container.transfers:
        assert b"CREATE" in schema
        assert b"INSERT INTO" not in schema
    assert container.exec_config == expected_initialization
    assert container.wait_strategy is not None


def test_redis_readiness_checks_for_server_errors() -> None:
    assert _redis.REDIS.ready_command == (
        "redis-cli",
        "-e",
        "-h",
        "127.0.0.1",
        "-p",
        "6379",
        "PING",
    )


def test_sql_server_readiness_requires_online_databases() -> None:
    assert _sql_server.SQL_SERVER.ready_command == (
        "/bin/bash",
        "-c",
        'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" exec /opt/mssql-tools18/bin/sqlcmd '
        '-S 127.0.0.1 -U sa -C -b -Q "SET NOCOUNT ON; '
        "IF EXISTS (SELECT 1 FROM sys.databases WHERE state_desc <> 'ONLINE') "
        "RAISERROR('not ready', 16, 1)\"",
    )


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


def test_sql_server_schema_failure_reports_sqlcmd_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        exec_result=ExecResult(exit_code=1, output=b"Incorrect syntax"),
        port=1433,
    )
    install_stub(monkeypatch, _sql_server, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)Incorrect syntax.*ready to accept connections",
    ):
        SQLServer().start()

    assert container.stopped


def test_cassandra_schema_failure_reports_cqlsh_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        exec_result=ExecResult(exit_code=2, output=b"invalid CQL"),
        port=9042,
    )
    install_stub(monkeypatch, _cassandra, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)invalid CQL.*ready to accept connections",
    ):
        Cassandra().start()

    assert container.stopped


def test_command_only_initialization_failure_uses_general_diagnostic() -> None:
    container = StubContainer(
        exec_result=ExecResult(exit_code=1, output=b"SET failed"),
        port=6379,
    )
    spec = replace(_redis.REDIS, initialize_command=("initialize",))

    with pytest.raises(RuntimeError) as error:
        DatabaseContainer(spec, container_factory=lambda _: container).start()

    message = str(error.value)
    assert message.startswith(
        "Could not initialize Redis; the client exited with 1"
    )
    assert "schema" not in message
    assert "SET failed" in message
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


@pytest.mark.parametrize(
    ("image", "repository"),
    [
        (POSTGRES_IMAGE, "postgres"),
        (MARIADB_IMAGE, "mariadb"),
        (CASSANDRA_IMAGE, "cassandra"),
        (REDIS_IMAGE, "redis"),
        (SQL_SERVER_IMAGE, "mcr.microsoft.com/mssql/server"),
    ],
)
def test_the_image_is_pinned_by_digest(image: str, repository: str) -> None:
    assert re.fullmatch(rf"{repository}:[^@\s]+@sha256:[0-9a-f]{{64}}", image)

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

    schema = (
        resources.files("database_conformance")
        .joinpath("sql_server.sql")
        .read_text(encoding="utf-8")
    )
    assert "CREATE TABLE [conformance].[items]" in schema
    assert "CREATE OR ALTER PROCEDURE [conformance].[noop]" in schema

    schema = (
        resources.files("database_conformance")
        .joinpath("cassandra.cql")
        .read_text(encoding="utf-8")
    )
    assert "CREATE KEYSPACE conformance" in schema
    assert "CREATE TABLE conformance.items" in schema
    assert "INSERT INTO" not in schema
