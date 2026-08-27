# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The PostgreSQL container lifecycle."""

from __future__ import annotations

import subprocess
from importlib import resources
from typing import Any

import pytest

from database_conformance import _postgres
from database_conformance._postgres import POSTGRES_IMAGE, Postgres

_CONTAINER_ID = "a" * 64


def completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class StubPostgres(Postgres):
    def __init__(
        self, responses: list[subprocess.CompletedProcess[str] | Exception]
    ) -> None:
        super().__init__()
        self.responses = responses
        self.commands: list[tuple[tuple[str, ...], str | None]] = []

    def _docker(
        self, *arguments: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append((arguments, stdin))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def ready_responses() -> list[subprocess.CompletedProcess[str]]:
    return [
        completed(stdout=f"{_CONTAINER_ID}\n"),
        completed(stdout="127.0.0.1:32768\n"),
        completed(stdout="true\n"),
        completed(),
        completed(),
        completed(),
    ]


def test_starts_initializes_publishes_and_removes_postgres() -> None:
    postgres = StubPostgres(ready_responses())

    with postgres:
        assert postgres.variables == {
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "32768",
            "POSTGRES_DATABASE": "conformance",
            "POSTGRES_USER": "conformance",
            "POSTGRES_PASSWORD": "conformance",
        }

    run, schema, remove = (
        postgres.commands[0],
        postgres.commands[4],
        postgres.commands[5],
    )
    assert run[0] == (
        "run",
        "--detach",
        "--rm",
        "--publish",
        "127.0.0.1::5432",
        "--env",
        "POSTGRES_DB=conformance",
        "--env",
        "POSTGRES_USER=conformance",
        "--env",
        "POSTGRES_PASSWORD=conformance",
        POSTGRES_IMAGE,
    )
    assert schema[0][:6] == (
        "exec",
        "--interactive",
        "--env",
        "PGPASSWORD=conformance",
        _CONTAINER_ID,
        "psql",
    )
    assert schema[1] is not None
    assert "CREATE SCHEMA IF NOT EXISTS conformance" in schema[1]
    assert "INSERT INTO" not in schema[1]
    assert remove[0] == ("rm", "--force", _CONTAINER_ID)


def test_retries_readiness_until_postgres_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_postgres.time, "sleep", lambda _: None)
    postgres = StubPostgres(
        [
            completed(stdout=f"{_CONTAINER_ID}\n"),
            completed(stdout="127.0.0.1:32768\n"),
            completed(stdout="true\n"),
            completed(returncode=1),
            completed(stdout="true\n"),
            completed(),
            completed(),
            completed(),
        ]
    )

    with postgres:
        pass

    readiness = [
        arguments
        for arguments, _ in postgres.commands
        if arguments[:2] == ("exec", _CONTAINER_ID)
    ]
    assert len(readiness) == 2


def test_an_invalid_port_mapping_cleans_up_the_container() -> None:
    postgres = StubPostgres(
        [
            completed(stdout=f"{_CONTAINER_ID}\n"),
            completed(stdout="not-a-port\n"),
            completed(),
        ]
    )

    with pytest.raises(RuntimeError, match="invalid PostgreSQL port mapping"):
        postgres.start()

    assert postgres.commands[-1][0] == ("rm", "--force", _CONTAINER_ID)


def test_an_early_exit_reports_logs_and_cleans_up() -> None:
    postgres = StubPostgres(
        [
            completed(stdout=f"{_CONTAINER_ID}\n"),
            completed(stdout="127.0.0.1:32768\n"),
            completed(stdout="false\n"),
            completed(stdout="database system is shut down\n"),
            completed(),
        ]
    )

    with pytest.raises(
        RuntimeError, match="database system is shut down"
    ):
        postgres.start()

    assert postgres.commands[-1][0] == ("rm", "--force", _CONTAINER_ID)


def test_a_readiness_timeout_reports_logs_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_postgres, "timeout_seconds", lambda *_: 0)
    postgres = StubPostgres(
        [
            completed(stdout=f"{_CONTAINER_ID}\n"),
            completed(stdout="127.0.0.1:32768\n"),
            completed(stdout="still starting\n"),
            completed(),
        ]
    )

    with pytest.raises(RuntimeError, match="did not become ready"):
        postgres.start()

    assert postgres.commands[-1][0] == ("rm", "--force", _CONTAINER_ID)


def test_a_schema_failure_reports_logs_and_cleans_up() -> None:
    postgres = StubPostgres(
        [
            completed(stdout=f"{_CONTAINER_ID}\n"),
            completed(stdout="127.0.0.1:32768\n"),
            completed(stdout="true\n"),
            completed(),
            completed(returncode=3, stderr="syntax error"),
            completed(stdout="ready to accept connections\n"),
            completed(),
        ]
    )

    with pytest.raises(RuntimeError, match="syntax error"):
        postgres.start()

    assert postgres.commands[-1][0] == ("rm", "--force", _CONTAINER_ID)


def test_missing_docker_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)

    with pytest.raises(RuntimeError, match="docker command was not found"):
        Postgres().start()


def test_the_schema_is_packaged_with_the_runner() -> None:
    schema = (
        resources.files("database_conformance")
        .joinpath("postgres.sql")
        .read_text(encoding="utf-8")
    )

    assert "CREATE TABLE IF NOT EXISTS conformance.items" in schema
    assert "CREATE OR REPLACE PROCEDURE conformance.noop()" in schema
