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

from database_conformance import _mariadb, _opensearch, _postgres
from database_conformance._container import _pull_reference
from database_conformance._mariadb import MARIADB_IMAGE, MariaDB
from database_conformance._opensearch import (
    OPENSEARCH,
    OPENSEARCH_IMAGE,
    OpenSearch,
)
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
        "bootstrap_marker",
        "expected_user",
        "expected_password",
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
            b"CREATE",
            "conformance",
            "conformance",
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
            b"CREATE",
            "conformance",
            "conformance",
        ),
        (
            _opensearch,
            OpenSearch,
            9200,
            {
                "discovery.type": "single-node",
                "DISABLE_INSTALL_DEMO_CONFIG": "true",
                "DISABLE_SECURITY_PLUGIN": "true",
                "OPENSEARCH_JAVA_OPTS": (
                    "-Xms512m -Xmx512m -Dlog4j2.disable.jmx=true"
                ),
            },
            b'"number_of_shards": 1',
            "",
            "",
        ),
    ],
)
def test_starts_initializes_publishes_and_removes_database(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: type[Postgres] | type[MariaDB] | type[OpenSearch],
    port: int,
    expected_environment: dict[str, str],
    bootstrap_marker: bytes,
    expected_user: str,
    expected_password: str,
) -> None:
    container = StubContainer(port=port)
    install_stub(monkeypatch, module, container)

    with backend_type() as database:
        assert database.variables == {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "32768",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": expected_user,
            "DATABASE_PASSWORD": expected_password,
        }

    assert container.started
    assert container.stopped
    assert container.env == expected_environment
    assert container.ports == {f"{port}/tcp": ("127.0.0.1", 0)}
    assert container.transfers
    bootstrap, path = container.transfers[0]
    assert path.startswith("/tmp/otel-conformance-")
    assert bootstrap_marker in bootstrap
    assert b"\r\n" not in bootstrap
    assert b"INSERT INTO" not in bootstrap
    assert container.wait_strategy is not None
    assert container.exec_config is not None


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


@pytest.mark.parametrize(
    ("module", "backend_type", "backend_name", "port"),
    [
        (_postgres, Postgres, "PostgreSQL", 5432),
        (_opensearch, OpenSearch, "OpenSearch", 9200),
    ],
)
def test_bootstrap_failure_reports_client_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: type[Postgres] | type[OpenSearch],
    backend_name: str,
    port: int,
) -> None:
    container = StubContainer(
        exec_result=ExecResult(exit_code=3, output=b"syntax error"),
        port=port,
    )
    install_stub(monkeypatch, module, container)

    with pytest.raises(
        RuntimeError,
        match=rf"(?s)Could not bootstrap {backend_name}.*syntax error.*"
        r"ready to accept connections",
    ):
        backend_type().start()

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

    name, separator, digest = OPENSEARCH_IMAGE.partition("@")
    assert name == "opensearchproject/opensearch:3.8.0"
    assert separator == "@"
    assert digest.startswith("sha256:")

    name, separator, digest = MARIADB_IMAGE.partition("@")
    assert name == "mariadb:11.8.9-noble"
    assert separator == "@"
    assert digest.startswith("sha256:")


def test_digest_pull_reference_omits_the_display_tag() -> None:
    assert (
        _pull_reference(
            "registry.example.test:5000/database:3.8.0@sha256:1234"
        )
        == "registry.example.test:5000/database@sha256:1234"
    )


def test_the_bootstrap_resources_are_packaged_with_the_runner() -> None:
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

    bootstrap = (
        resources.files("database_conformance")
        .joinpath("opensearch-bootstrap.sh")
        .read_text(encoding="utf-8")
    )
    assert '"number_of_shards": 1' in bootstrap
    assert '{"name":"alpha","description":"first conformance document"}' in (
        bootstrap
    )


def test_opensearch_waits_for_cluster_health_before_bootstrap() -> None:
    assert OPENSEARCH.ready_command == (
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "http://127.0.0.1:9200/_cluster/health"
        "?wait_for_status=yellow&timeout=1s",
    )
    assert OPENSEARCH.startup_timeout_seconds == 180.0
