# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The PostgreSQL-backed database session factory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import database_conformance


def test_database_session_injects_backend_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured: dict[str, Any] = {}
    session = object()

    class StubPostgres:
        variables = {
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "54321",
            "POSTGRES_DATABASE": "conformance",
            "POSTGRES_USER": "conformance",
            "POSTGRES_PASSWORD": "conformance",
        }

        def __enter__(self) -> StubPostgres:
            events.append("postgres-enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append("postgres-exit")

    @contextmanager
    def stub_session(
        directory: Path | str, **kwargs: Any
    ) -> Generator[object, None, None]:
        events.append("session-enter")
        captured["directory"] = directory
        captured.update(kwargs)
        try:
            yield session
        finally:
            events.append("session-exit")

    monkeypatch.setattr(database_conformance, "Postgres", StubPostgres)
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    with database_conformance.database_session(
        "package",
        variables={"POSTGRES_HOST": "wrong", "CUSTOM": "value"},
    ) as running:
        assert running is session
        assert events == ["postgres-enter", "session-enter"]

    assert captured["directory"] == "package"
    assert captured["variables"] == {
        "CUSTOM": "value",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "54321",
        "POSTGRES_DATABASE": "conformance",
        "POSTGRES_USER": "conformance",
        "POSTGRES_PASSWORD": "conformance",
    }
    assert events == [
        "postgres-enter",
        "session-enter",
        "session-exit",
        "postgres-exit",
    ]


def test_database_session_closes_postgres_after_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class StubPostgres:
        variables: dict[str, str] = {}

        def __enter__(self) -> StubPostgres:
            return self

        def __exit__(self, *args: object) -> None:
            nonlocal closed
            closed = True

    @contextmanager
    def stub_session(
        directory: Path | str, **kwargs: Any
    ) -> Generator[object, None, None]:
        del directory, kwargs
        yield object()

    monkeypatch.setattr(database_conformance, "Postgres", StubPostgres)
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    with pytest.raises(RuntimeError, match="scenario failed"):
        with database_conformance.database_session("package"):
            raise RuntimeError("scenario failed")

    assert closed
