# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The PostgreSQL container lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

import pytest
from docker.errors import DockerException
from testcontainers.core.container import ExecConfig

from database_conformance import _postgres
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
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.exec_result = exec_result or ExecResult()
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
        assert port == 5432
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
    monkeypatch: pytest.MonkeyPatch, container: StubContainer
) -> None:
    monkeypatch.setattr(_postgres, "DockerContainer", lambda _: container)


def test_starts_initializes_publishes_and_removes_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer()
    install_stub(monkeypatch, container)

    with Postgres() as postgres:
        assert postgres.variables == {
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "32768",
            "POSTGRES_DATABASE": "conformance",
            "POSTGRES_USER": "conformance",
            "POSTGRES_PASSWORD": "conformance",
        }

    assert container.started
    assert container.stopped
    assert container.env == {
        "POSTGRES_DB": "conformance",
        "POSTGRES_USER": "conformance",
        "POSTGRES_PASSWORD": "conformance",
    }
    assert container.ports == {"5432/tcp": ("127.0.0.1", 0)}
    assert container.transfers
    schema, path = container.transfers[0]
    assert path == "/tmp/otel-conformance-postgres.sql"
    assert b"CREATE SCHEMA IF NOT EXISTS conformance" in schema
    assert b"INSERT INTO" not in schema
    assert container.wait_strategy is not None
    assert container.exec_config is not None
    assert container.exec_config.command[-2:] == [
        "--file",
        "/tmp/otel-conformance-postgres.sql",
    ]
    assert container.exec_config.environment == {
        "PGPASSWORD": "conformance"
    }


def test_start_failure_cleans_up_the_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(start_error=RuntimeError("startup failed"))
    install_stub(monkeypatch, container)

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
    install_stub(monkeypatch, container)

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
    install_stub(monkeypatch, container)

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
    install_stub(monkeypatch, container)
    postgres = Postgres().start()

    with pytest.raises(RuntimeError, match="already been started"):
        postgres.start()

    postgres.close()


def test_the_image_is_pinned_by_digest() -> None:
    name, separator, digest = POSTGRES_IMAGE.partition("@")

    assert name == "postgres:18.6-bookworm"
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
