# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Reading a conformance directory's identity out of its path."""

from __future__ import annotations

from pathlib import Path

import pytest

from conformance_report import discover
from conftest import write_target


def test_a_directory_with_no_reduction_is_not_a_target(tmp_path: Path) -> None:
    """Never run to completion is an absent measurement, not a failing one."""
    write_target(tmp_path, "demo/python/a/opentelemetry-a")
    unfinished = tmp_path / "scenarios" / "demo" / "python" / "b" / "otel-b"
    unfinished.mkdir(parents=True)
    (unfinished / "conformance.yaml").write_text(
        "runner: demo-conformance\ninstrumented_library: b\n"
        'instrumentation_library: otel-b\nscenarios:\n  main:\n    run: "true"\n',
        encoding="utf-8",
    )
    assert [t.id for t in discover(tmp_path)] == [
        "demo/python/a/opentelemetry-a"
    ]


def test_the_side_segment_is_recognised(tmp_path: Path) -> None:
    write_target(tmp_path, "http/java/okhttp/opentelemetry-javaagent/client")
    (target,) = discover(tmp_path)
    assert (target.domain, target.language, target.side) == (
        "http",
        "java",
        "client",
    )
    assert target.library == "okhttp"
    assert target.instrumentation == "opentelemetry-javaagent"


@pytest.mark.parametrize(
    "identifier",
    [
        "demo/python/demo/opentelemetry-demo/extra",
        "http/java/okhttp/opentelemetry-javaagent/unknown",
        "database/java/jdbc/opentelemetry-javaagent",
    ],
)
def test_an_unsupported_layout_is_an_error(
    tmp_path: Path, identifier: str
) -> None:
    write_target(tmp_path, identifier)
    with pytest.raises(ValueError, match="supported"):
        discover(tmp_path)


@pytest.mark.parametrize("backend", ["mariadb", "postgresql"])
@pytest.mark.parametrize(
    "instrumentation", ["opentelemetry-javaagent", "opentelemetry-library"]
)
def test_database_layout(
    tmp_path: Path, backend: str, instrumentation: str
) -> None:
    write_target(tmp_path, f"database/java/{backend}/jdbc/{instrumentation}")
    (target,) = discover(tmp_path)
    assert target.backend == backend
    assert target.library == "jdbc"
    assert target.instrumentation == instrumentation
    assert target.side is None


def test_a_layout_too_shallow_to_read_is_an_error(tmp_path: Path) -> None:
    write_target(tmp_path, "demo/python/demo")
    with pytest.raises(ValueError, match="domain"):
        discover(tmp_path)


def test_what_a_dependency_or_a_build_left_behind_is_not_a_target(
    tmp_path: Path,
) -> None:
    """A checkout that has run the scenarios is full of build artifacts.

    `uv run` leaves a `.venv` beside the scenario, `npm ci` a `node_modules`,
    Gradle a `build`, and a package inside any of those may ship its own
    `conformance.yaml`. Discovering one would invent a target whose path does
    not name a domain, so the report would fail to build for whoever had just
    run the scenarios.
    """
    write_target(tmp_path, "demo/python/demo/opentelemetry-demo")
    for artifact in (".venv", "node_modules", "build"):
        write_target(
            tmp_path,
            f"demo/python/demo/opentelemetry-demo/{artifact}/vendored",
        )

    assert [t.id for t in discover(tmp_path)] == [
        "demo/python/demo/opentelemetry-demo"
    ]
