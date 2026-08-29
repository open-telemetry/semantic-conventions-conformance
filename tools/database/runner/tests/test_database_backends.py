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

from database_conformance import _hbase, _mariadb, _postgres
from database_conformance._hbase import (
    HBASE_1_IMAGE,
    HBASE_2_IMAGE,
    HBASE_MASTER_PORT,
    HBASE_REGIONSERVER_PORT,
    HBASE_ZOOKEEPER_PORT,
    HBase1,
    HBase2,
)
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
        log_error: Exception | None = None,
        exec_result: ExecResult | None = None,
        port: int = 5432,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.log_error = log_error
        self.exec_result = exec_result or ExecResult()
        self.port = port
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
        return 32768

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
    assert container.exec_config is not None


class StubImage:
    def __init__(self, *, build_error: DockerException | None = None) -> None:
        self.build_error = build_error
        self.built = False
        self.removed = False

    def build(self) -> StubImage:
        if self.build_error is not None:
            raise self.build_error
        self.built = True
        return self

    def remove(self) -> None:
        self.removed = True


def test_hbase_builds_initializes_and_removes_the_upstream_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(port=HBASE_ZOOKEEPER_PORT)
    image = StubImage()
    image_arguments: dict[str, Any] = {}

    def image_factory(**kwargs: Any) -> StubImage:
        image_arguments.update(kwargs)
        return image

    install_stub(monkeypatch, _hbase, container)
    monkeypatch.setattr(_hbase, "DockerImage", image_factory)
    with HBase1() as database:
        assert database.variables == {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "32768",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": "",
            "DATABASE_PASSWORD": "",
        }

    assert image.built
    assert image.removed
    assert image_arguments["tag"] == HBASE_1_IMAGE
    assert image_arguments["buildargs"] == {
        "HBASE_VERSION": "1.7.2",
        "HBASE_SHA512": (
            "43c633606f4316319d0e872862bfee935a191308239ca42ad9545402fb9a83f9"
            "399845123bdcda60c315bcb09bd7555375b73afcb3d668453d56e3985bf284fa"
        ),
    }
    assert container.started
    assert container.stopped
    assert container.kwargs == {"hostname": "localhost"}
    assert container.ports == {
        f"{HBASE_ZOOKEEPER_PORT}/tcp": ("127.0.0.1", HBASE_ZOOKEEPER_PORT),
        f"{HBASE_MASTER_PORT}/tcp": ("127.0.0.1", HBASE_MASTER_PORT),
        f"{HBASE_REGIONSERVER_PORT}/tcp": (
            "127.0.0.1",
            HBASE_REGIONSERVER_PORT,
        ),
    }
    assert container.exec_config is not None
    assert container.exec_config.command == [
        "hbase",
        "shell",
        "-n",
        "/tmp/otel-conformance-hbase.rb",
    ]


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
        HBase2().start()

    assert image.removed


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

    schema = (
        resources.files("database_conformance")
        .joinpath("hbase.rb")
        .read_text(encoding="utf-8")
    )
    assert "create 'conformance:items', 'data'" in schema
    assert "put 'conformance:items', 'seed', 'data:name', 'seed'" in schema


def test_hbase_fixture_uses_pinned_upstream_inputs() -> None:
    assert HBASE_1_IMAGE == "otel-conformance-hbase:1.7.2"
    assert HBASE_2_IMAGE == "otel-conformance-hbase:2.4.18"
    dockerfile = (
        resources.files("database_conformance")
        .joinpath("hbase-image", "Dockerfile")
        .read_text(encoding="utf-8")
    )

    assert (
        "FROM eclipse-temurin:8-jre-jammy@sha256:"
        "d53aa7811eba390450721b1037978605992f5d9467c4af629384f23a49f78436"
        in dockerfile
    )
    assert "ARG HBASE_VERSION=2.4.18" in dockerfile
    assert "ARG HBASE_SHA512=" in dockerfile
    assert "sha512sum --check --strict" in dockerfile
