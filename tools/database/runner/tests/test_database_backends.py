# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Managed database container lifecycles."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from importlib import resources
from typing import Any

import pytest
from docker.errors import DockerException
from testcontainers.core.container import ExecConfig

from database_conformance import (
    _hbase,
    _mariadb,
    _postgres,
    _redis,
    _sql_server,
)
from database_conformance._container import DatabaseContainer
from database_conformance._hbase import (
    HBASE_IMAGE,
    HBASE_MASTER_PORT,
    HBASE_REGIONSERVER_PORT,
    HBase,
)
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
        log_error: Exception | None = None,
        exec_result: ExecResult | None = None,
        port: int = 5432,
        published_port: int = 32768,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.log_error = log_error
        self.exec_result = exec_result or ExecResult()
        self.port = port
        self.published_port = published_port
        self.env: dict[str, str] = {}
        self.kwargs: dict[str, Any] = {}
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

    def with_kwargs(self, **kwargs: Any) -> StubContainer:
        self.kwargs = kwargs
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
        return self.published_port

    def exec(self, config: ExecConfig) -> ExecResult:
        self.exec_config = config
        return self.exec_result

    def get_logs(self) -> tuple[bytes, bytes]:
        if self.log_error is not None:
            raise self.log_error
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
    backend_type: type[Postgres]
    | type[MariaDB]
    | type[Redis]
    | type[SQLServer],
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


class StubImage:
    def __init__(
        self,
        *,
        build_error: BaseException | None = None,
        remove_error: DockerException | None = None,
    ) -> None:
        self.build_error = build_error
        self.remove_error = remove_error
        self.built = False
        self.removed = False
        self.remove_calls = 0

    def build(self) -> StubImage:
        if self.build_error is not None:
            raise self.build_error
        self.built = True
        return self

    def remove(self) -> None:
        self.remove_calls += 1
        if self.remove_error is not None:
            raise self.remove_error
        self.removed = True


def test_hbase_builds_initializes_and_removes_the_upstream_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        port=HBASE_MASTER_PORT,
        published_port=HBASE_MASTER_PORT,
    )
    image = StubImage()
    image_arguments: dict[str, Any] = {}

    def image_factory(**kwargs: Any) -> StubImage:
        image_arguments.update(kwargs)
        return image

    install_stub(monkeypatch, _hbase, container)
    monkeypatch.setattr(_hbase, "DockerImage", image_factory)
    with HBase() as database:
        assert database.variables == {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "16000",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": "",
            "DATABASE_PASSWORD": "",
        }

    assert image.built
    assert image.removed
    assert image_arguments["tag"] == HBASE_IMAGE
    assert image_arguments["clean_up"] is True
    assert image_arguments["buildargs"] == {
        "HBASE_VERSION": "3.0.0",
        "HBASE_SHA512": (
            "8290bc3cece084d36f7f47aae726268c7332e4828c6e8599df1343b03348e93f"
            "91165fad03ac6107bfbf0d8535e72024fa5d19217890d2848d013d8418a584ed"
        ),
    }
    assert container.started
    assert container.stopped
    assert container.kwargs == {"hostname": "localhost"}
    assert container.ports == {
        f"{HBASE_MASTER_PORT}/tcp": ("127.0.0.1", HBASE_MASTER_PORT),
        f"{HBASE_REGIONSERVER_PORT}/tcp": (
            "127.0.0.1",
            HBASE_REGIONSERVER_PORT,
        ),
    }
    assert "2181/tcp" not in container.ports
    assert container.exec_config is not None
    assert container.exec_config.command == [
        "hbase",
        "shell",
        "-n",
        "/tmp/otel-conformance-hbase.rb",
    ]
    assert len(container.transfers) == 1
    schema, destination = container.transfers[0]
    assert destination == "/tmp/otel-conformance-hbase.rb"
    assert b"put 'conformance:items', 'seed', 'data:name', 'seed'" in schema


def test_hbase_image_build_failure_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = StubImage(build_error=DockerException("builder unavailable"))
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)

    with pytest.raises(
        RuntimeError,
        match=(
            "Could not build the HBase fixture from the Apache HBase "
            "distribution: builder unavailable"
        ),
    ):
        HBase().start()

    assert image.removed


@pytest.mark.parametrize(
    "error", [RuntimeError("build interrupted"), KeyboardInterrupt()]
)
def test_hbase_cleans_up_unexpected_build_failures(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    image = StubImage(build_error=error)
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)
    with pytest.raises(type(error)) as caught:
        HBase().start()
    assert caught.value is error
    assert image.removed
    assert image.remove_calls == 1


def test_hbase_preserves_build_and_image_cleanup_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = StubImage(
        build_error=DockerException("builder unavailable"),
        remove_error=DockerException("image removal failed"),
    )
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)
    with pytest.raises(
        RuntimeError,
        match=r"(?s)builder unavailable.*HBase fixture cleanup also failed: "
        r"image removal failed",
    ):
        HBase().start()


@pytest.mark.parametrize("stage", ["configuration", "start", "initialization"])
def test_hbase_removes_its_image_on_container_failures(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    container = StubContainer(
        port=HBASE_MASTER_PORT,
        start_error=RuntimeError("startup failed") if stage == "start" else None,
        exec_result=ExecResult(exit_code=1, output=b"schema failed")
        if stage == "initialization"
        else None,
    )
    if stage == "configuration":
        def fail_configuration(**_: Any) -> None:
            raise RuntimeError("configuration failed")
        monkeypatch.setattr(container, "with_kwargs", fail_configuration)
    image = StubImage()
    install_stub(monkeypatch, _hbase, container)
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)
    with pytest.raises(RuntimeError, match="failed"):
        HBase().start()
    assert image.removed
    assert image.remove_calls == 1
    assert container.stopped is (stage != "configuration")


def test_hbase_removes_its_fixture_after_scenario_setup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(port=HBASE_MASTER_PORT)
    image = StubImage()
    install_stub(monkeypatch, _hbase, container)
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)
    with pytest.raises(RuntimeError, match="setup failed"):
        with HBase():
            raise RuntimeError("setup failed")
    assert container.stopped
    assert image.removed
    assert image.remove_calls == 1


def test_hbase_cannot_build_a_second_image_while_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(port=HBASE_MASTER_PORT)
    image = StubImage()
    install_stub(monkeypatch, _hbase, container)
    monkeypatch.setattr(_hbase, "DockerImage", lambda **_: image)
    with HBase() as backend:
        with pytest.raises(RuntimeError, match="already been started"):
            backend.start()
        assert not container.stopped
        assert not image.removed
    assert image.remove_calls == 1


def test_start_failure_cleans_up_the_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(start_error=RuntimeError("startup failed"))
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)Could not start PostgreSQL: startup failed.*"
        r"ready to accept connections",
    ):
        Postgres().start()

    assert container.stopped


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit])
def test_start_control_flow_exception_is_preserved_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
) -> None:
    container = StubContainer(start_error=error_type())
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(error_type):
        Postgres().start()

    assert container.stopped


def test_start_failure_survives_unavailable_container_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        start_error=RuntimeError("startup failed"),
        log_error=RuntimeError("container not started"),
    )
    install_stub(monkeypatch, _postgres, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)Could not start PostgreSQL: startup failed.*"
        r"Could not read PostgreSQL logs: container not started",
    ):
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
        match=r"(?s)Could not start PostgreSQL: startup failed.*"
        r"PostgreSQL cleanup also failed: cleanup failed",
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
        .joinpath("hbase.rb")
        .read_text(encoding="utf-8")
    )
    assert "create 'conformance:items', 'data'" in schema
    assert "put 'conformance:items', 'seed', 'data:name', 'seed'" in schema


def test_hbase_fixture_uses_pinned_upstream_inputs() -> None:
    assert HBASE_IMAGE == "otel-conformance-hbase:3.0.0"
    dockerfile = (
        resources.files("database_conformance")
        .joinpath("hbase-image", "Dockerfile")
        .read_text(encoding="utf-8")
    )

    assert (
        "FROM eclipse-temurin:17-jre-jammy@sha256:"
        "c35794d1348777e6bc310b9b7f420098ef8f37e988199549b545fded79a895a2"
        in dockerfile
    )
    assert f"ARG HBASE_VERSION={_hbase.HBASE_VERSION}" in dockerfile
    assert f"ARG HBASE_SHA512={_hbase._HBASE_SHA512}" in dockerfile
    assert "sha512sum --check --strict" in dockerfile
