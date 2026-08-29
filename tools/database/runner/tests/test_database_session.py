# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The configured database session factory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import database_conformance
from opentelemetry.conformance import SpecError


def test_database_session_injects_backend_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    captured: dict[str, Any] = {}
    session = object()

    class StubBackend:
        variables = {
            "DATABASE_HOST": "127.0.0.1",
            "DATABASE_PORT": "54321",
            "DATABASE_NAME": "conformance",
            "DATABASE_USER": "conformance",
            "DATABASE_PASSWORD": "conformance",
        }

        def __enter__(self) -> StubBackend:
            events.append("backend-enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append("backend-exit")

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

    monkeypatch.setitem(
        database_conformance._BACKENDS, "postgresql", StubBackend
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    (tmp_path / "database.yaml").write_text(
        "backend: postgresql\n", encoding="utf-8"
    )
    with database_conformance.database_session(
        tmp_path,
        variables={"DATABASE_HOST": "wrong", "CUSTOM": "value"},
    ) as running:
        assert running is session
        assert events == ["backend-enter", "session-enter"]

    assert captured["directory"] == tmp_path
    assert captured["variables"] == {
        "CUSTOM": "value",
        "DATABASE_HOST": "127.0.0.1",
        "DATABASE_PORT": "54321",
        "DATABASE_NAME": "conformance",
        "DATABASE_USER": "conformance",
        "DATABASE_PASSWORD": "conformance",
    }
    assert events == [
        "backend-enter",
        "session-enter",
        "session-exit",
        "backend-exit",
    ]


def test_database_session_closes_mariadb_after_an_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    closed = False

    class StubBackend:
        variables: dict[str, str] = {}

        def __enter__(self) -> StubBackend:
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

    monkeypatch.setitem(database_conformance._BACKENDS, "mariadb", StubBackend)
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    (tmp_path / "database.yaml").write_text(
        "backend: mariadb\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="scenario failed"):
        with database_conformance.database_session(tmp_path):
            raise RuntimeError("scenario failed")

    assert closed


def test_database_session_dispatches_couchbase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    entered = False

    class StubBackend:
        variables: dict[str, str] = {}

        def __enter__(self) -> StubBackend:
            nonlocal entered
            entered = True
            return self

        def __exit__(self, *args: object) -> None:
            pass

    @contextmanager
    def stub_session(
        directory: Path | str, **kwargs: Any
    ) -> Generator[object, None, None]:
        del directory, kwargs
        yield object()

    monkeypatch.setitem(
        database_conformance._BACKENDS, "couchbase", StubBackend
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )
    (tmp_path / "database.yaml").write_text(
        "backend: couchbase\n", encoding="utf-8"
    )

    with database_conformance.database_session(tmp_path):
        assert entered


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("backend: sqlite\n", "unsupported backend 'sqlite'"),
        ("backend: [postgresql]\n", "exactly one string key"),
        ("backend: postgresql\nextra: value\n", "exactly one string key"),
    ],
)
def test_database_session_rejects_invalid_backend_configuration(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    (tmp_path / "database.yaml").write_text(contents, encoding="utf-8")

    with pytest.raises(SpecError, match=message):
        with database_conformance.database_session(tmp_path):
            pass
