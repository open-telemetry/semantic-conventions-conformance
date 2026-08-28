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


def test_a_trailing_segment_that_is_not_a_side_is_not_one(
    tmp_path: Path,
) -> None:
    """Only the two the HTTP domain splits on; anything else is a slug."""
    write_target(tmp_path, "demo/python/demo/opentelemetry-demo/extra")
    (target,) = discover(tmp_path)
    assert target.side is None


def test_a_layout_too_shallow_to_read_is_an_error(tmp_path: Path) -> None:
    write_target(tmp_path, "demo/python/demo")
    with pytest.raises(ValueError, match="domain"):
        discover(tmp_path)


def test_what_a_dependency_or_a_build_left_behind_is_not_a_target(
    tmp_path: Path,
) -> None:
    """A checkout that has run the scenarios is a checkout full of artifacts.

    `uv run` leaves a `.venv` beside the scenario, `npm ci` a `node_modules`,
    Gradle a `build` — and a package inside any of those is free to ship a file
    called `conformance.yaml`. Discovered, it would invent a target whose path
    does not name a domain, so the report would fail to build on the machine of
    whoever had just run the scenarios.
    """
    write_target(tmp_path, "demo/python/demo/opentelemetry-demo")
    for artifact in (".venv", "node_modules", "build"):
        write_target(
            tmp_path, f"demo/python/demo/opentelemetry-demo/{artifact}/vendored"
        )

    assert [t.id for t in discover(tmp_path)] == [
        "demo/python/demo/opentelemetry-demo"
    ]
