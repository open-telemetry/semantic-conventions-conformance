# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The configured database session factory."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import database_conformance
from database_conformance._hbase import HBase
from database_conformance._mongodb import MongoDB
from database_conformance._mysql import MySQL
from database_conformance._oracle import Oracle
from database_conformance._redis import Redis
from database_conformance._registry import BACKENDS
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


@pytest.mark.parametrize("backend", ["postgresql", "hbase"])
def test_database_session_injects_backend_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backend: str,
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
        database_conformance._BACKEND_REGISTRY,
        backend,
        replace(
            database_conformance._BACKEND_REGISTRY[backend],
            factory=StubBackend,
        ),
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    spec = _write_spec(tmp_path, f"  backend: {backend}")
    with database_conformance.database_session(
        tmp_path,
        variables={"DATABASE_HOST": "wrong", "CUSTOM": "value"},
        spec=spec,
    ) as running:
        assert running is session
        assert events == ["backend-enter", "session-enter"]

    assert captured["directory"] == tmp_path
    assert captured["spec"] is spec
    assert "build_data" not in captured
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


def test_hbase_registers_its_factory_and_span_type() -> None:
    registration = BACKENDS["hbase"]
    assert registration.factory is HBase
    assert registration.system == "hbase"
    assert registration.client_span_type == "db.hbase.client"


@pytest.mark.parametrize(
    "backend, backend_type",
    [("mongodb", MongoDB), ("oracle", Oracle), ("redis", Redis)],
)
def test_database_session_closes_backend_after_an_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backend: str,
    backend_type: type[MongoDB] | type[Oracle] | type[Redis],
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

    assert (
        database_conformance._BACKEND_REGISTRY[backend].factory is backend_type
    )
    monkeypatch.setitem(
        database_conformance._BACKEND_REGISTRY,
        backend,
        replace(
            database_conformance._BACKEND_REGISTRY[backend],
            factory=StubBackend,
        ),
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )

    spec = _write_spec(tmp_path, f"  backend: {backend}")
    with pytest.raises(RuntimeError, match="scenario failed"):
        with database_conformance.database_session(tmp_path, spec=spec):
            raise RuntimeError("scenario failed")

    assert closed


def test_database_session_dispatches_and_closes_cassandra(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class StubBackend:
        variables = {"DATABASE_LOCAL_DATACENTER": "datacenter1"}

        def __enter__(self) -> StubBackend:
            events.append("cassandra-enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append("cassandra-exit")

    @contextmanager
    def stub_session(
        directory: Path | str, **kwargs: Any
    ) -> Generator[object, None, None]:
        del directory
        assert kwargs["variables"] == {
            "DATABASE_LOCAL_DATACENTER": "datacenter1"
        }
        events.append("session-enter")
        try:
            yield object()
        finally:
            events.append("session-exit")

    monkeypatch.setitem(
        database_conformance._BACKEND_REGISTRY,
        "cassandra",
        replace(
            database_conformance._BACKEND_REGISTRY["cassandra"],
            factory=StubBackend,
        ),
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )
    spec = _write_spec(tmp_path, "  backend: cassandra")

    with pytest.raises(RuntimeError, match="scenario failed"):
        with database_conformance.database_session(tmp_path, spec=spec):
            raise RuntimeError("scenario failed")

    assert events == [
        "cassandra-enter",
        "session-enter",
        "session-exit",
        "cassandra-exit",
    ]


def test_database_session_dispatches_mysql(
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

    registration = database_conformance._BACKEND_REGISTRY["mysql"]
    assert registration.factory is MySQL
    assert registration.system == "mysql"
    assert registration.client_span_type == "db.mysql.client"

    monkeypatch.setitem(
        database_conformance._BACKEND_REGISTRY,
        "mysql",
        replace(registration, factory=StubBackend),
    )
    monkeypatch.setattr(
        database_conformance,
        "DOMAIN",
        SimpleNamespace(session=stub_session),
    )
    spec = _write_spec(tmp_path, "  backend: mysql")

    with database_conformance.database_session(tmp_path, spec=spec):
        assert entered


@pytest.mark.parametrize(
    ("runner_config", "message"),
    [
        ("  backend: sqlite", "unsupported backend 'sqlite'"),
        ("  backend: hbase-1", "unsupported backend 'hbase-1'"),
        ("  backend: hbase-2", "unsupported backend 'hbase-2'"),
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
