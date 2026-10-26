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

from database_conformance import _mariadb, _postgres, _redis
from database_conformance._container import DatabaseContainer
from database_conformance._mariadb import MARIADB_IMAGE, MariaDB
from database_conformance._postgres import POSTGRES_IMAGE, Postgres
from database_conformance._redis import REDIS_IMAGE, Redis


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
    ],
)
def test_starts_initializes_publishes_and_removes_database(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: type[Postgres] | type[MariaDB] | type[Redis],
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
