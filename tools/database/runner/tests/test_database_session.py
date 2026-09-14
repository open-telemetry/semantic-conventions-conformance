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
from opentelemetry.conformance import PackageSpec, SpecError, load_spec


def _write_spec(tmp_path: Path, runner_config: str) -> PackageSpec:
    (tmp_path / "conformance.yaml").write_text(
        f"""
runner: database-conformance
runner_config:
{runner_config}
instrumented_library: jdbc
instrumentation_library: demo
scenarios:
  statement:
    run: command
""",
        encoding="utf-8",
    )
    return load_spec(tmp_path)


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

    spec = _write_spec(tmp_path, "  backend: postgresql")
    with database_conformance.database_session(
        tmp_path,
        variables={
            "DATABASE_BACKEND": "wrong",
            "DATABASE_HOST": "wrong",
            "CUSTOM": "value",
        },
        spec=spec,
    ) as running:
        assert running is session
        assert events == ["backend-enter", "session-enter"]

    assert captured["directory"] == tmp_path
    assert captured["spec"] is spec
    assert "build_data" not in captured
    assert captured["variables"] == {
        "CUSTOM": "value",
        "DATABASE_BACKEND": "postgresql",
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

    spec = _write_spec(tmp_path, "  backend: mariadb")
    with pytest.raises(RuntimeError, match="scenario failed"):
        with database_conformance.database_session(tmp_path, spec=spec):
            raise RuntimeError("scenario failed")

    assert closed


@pytest.mark.parametrize(
    ("runner_config", "message"),
    [
        ("  backend: sqlite", "unsupported backend 'sqlite'"),
        ("  backend: [postgresql]", "expected a string"),
        (
            "  backend: postgresql\n  extra: value",
            "exactly one string key",
        ),
        ("  other: postgresql", "exactly one string key"),
        ("  {}", "exactly one string key"),
    ],
)
def test_database_session_rejects_invalid_backend_configuration(
    tmp_path: Path,
    runner_config: str,
    message: str,
) -> None:
    spec = _write_spec(tmp_path, runner_config)

    with pytest.raises(
        SpecError,
        match=rf"conformance\.yaml\.runner_config.*{message}",
    ):
        with database_conformance.database_session(tmp_path, spec=spec):
            pass
