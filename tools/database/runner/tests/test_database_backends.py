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

from database_conformance import _elasticsearch, _mariadb, _postgres
from database_conformance._elasticsearch import (
    ELASTICSEARCH,
    ELASTICSEARCH_IMAGE,
    Elasticsearch,
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
        exec_result: ExecResult | None = None,
        published_ports: dict[int, int] | None = None,
    ) -> None:
        self.start_error = start_error
        self.stop_error = stop_error
        self.exec_result = exec_result or ExecResult()
        self.published_ports = published_ports or {5432: 32768}
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
        return self.published_ports[port]

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
        "ports",
        "expected_environment",
        "expected_variables",
    ),
    [
        (
            _postgres,
            Postgres,
            {5432: 32768},
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
        ),
        (
            _mariadb,
            MariaDB,
            {3306: 32768},
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
        ),
        (
            _elasticsearch,
            Elasticsearch,
            {9200: 32768, 9300: 32769},
            {
                "discovery.type": "single-node",
                "xpack.security.enabled": "false",
                "ES_JAVA_OPTS": "-Xms256m -Xmx256m",
            },
            {
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": "32768",
                "DATABASE_NAME": "conformance",
                "DATABASE_USER": "",
                "DATABASE_PASSWORD": "",
                "DATABASE_TRANSPORT_PORT": "32769",
            },
        ),
    ],
)
def test_starts_initializes_publishes_and_removes_database(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    backend_type: type[Postgres] | type[MariaDB] | type[Elasticsearch],
    ports: dict[int, int],
    expected_environment: dict[str, str],
    expected_variables: dict[str, str],
) -> None:
    container = StubContainer(published_ports=ports)
    install_stub(monkeypatch, module, container)

    with backend_type() as database:
        assert database.variables == expected_variables

    assert container.started
    assert container.stopped
    assert container.env == expected_environment
    assert container.ports == {
        f"{port}/tcp": ("127.0.0.1", 0) for port in ports
    }
    assert container.transfers
    bootstrap, path = container.transfers[0]
    assert path.startswith("/tmp/otel-conformance-")
    if backend_type is Elasticsearch:
        assert b'"dynamic": "strict"' in bootstrap
        assert b'"index.number_of_shards": 1' in bootstrap
    else:
        assert b"CREATE" in bootstrap
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


def test_schema_failure_reports_client_output_and_logs(
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


def test_elasticsearch_schema_failure_reports_curl_output_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = StubContainer(
        exec_result=ExecResult(
            exit_code=22, output=b"index bootstrap rejected"
        ),
        published_ports={9200: 32768, 9300: 32769},
    )
    install_stub(monkeypatch, _elasticsearch, container)

    with pytest.raises(
        RuntimeError,
        match=r"(?s)index bootstrap rejected.*ready to accept connections",
    ):
        Elasticsearch().start()

    assert container.stopped


def test_elasticsearch_readiness_waits_for_a_yellow_cluster() -> None:
    assert ELASTICSEARCH.ready_command == (
        "sh",
        "-c",
        "curl --fail --silent "
        "'http://127.0.0.1:9200/_cluster/health"
        "?wait_for_status=yellow&timeout=1s' "
        "| grep --quiet '\"timed_out\":false'",
    )


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

    name, separator, digest = ELASTICSEARCH_IMAGE.partition("@")
    assert name == "docker.elastic.co/elasticsearch/elasticsearch:7.17.29"
    assert separator == "@"
    assert digest.startswith("sha256:")


def test_the_schema_files_are_packaged_with_the_runner() -> None:
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
        .joinpath("elasticsearch.json")
        .read_text(encoding="utf-8")
    )
    assert '"dynamic": "strict"' in bootstrap
    assert '"index.number_of_replicas": 0' in bootstrap
