# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Collecting ``conformance.yaml`` as a test file.

A scenario directory already declares everything a test needs, so no repo
should have to write a module that points at it. These run pytest inside
pytest, with a stub factory standing in for a real session — starting weaver
is the session's job, not the plugin's.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentelemetry.conformance import (
    ScenarioReport,
    WeaverNotInstalledError,
    _runners,
    pytest_plugin,
)

pytest_plugins = ["pytester"]

SPEC = """
runner: demo-conformance
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
  tool_calling:
    run: python tool_calling.py
"""


class FakeSession:
    """A session that never starts weaver, failing whichever scenarios it is told."""

    def __init__(self, failing: frozenset[str]) -> None:
        self._failing = failing

    def run(self, name: str) -> ScenarioReport:
        return ScenarioReport(
            name=name,
            failures=[f"{name}: nope"] if name in self._failing else [],
        )


@pytest.fixture(name="scenarios")
def _scenarios(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch):
    """A scenario directory, with a stub wrapper registered for its ``runner:``.

    ``pytester`` runs the inner pytest in this process, so both patches reach
    it — and both are undone afterwards, which registering the stub from a
    generated conftest would not be.
    """
    monkeypatch.setattr(pytest_plugin, "check_weaver", lambda: None)

    def build(failing: frozenset[str] = frozenset()) -> None:
        @contextmanager
        def factory(directory: Path, **_kwargs: object):
            # Where the session was opened, for the test that counts them.
            with Path("opened.log").open("a") as log:
                log.write(f"{directory}\n")
            yield FakeSession(failing)

        entry = SimpleNamespace(
            name="demo-conformance",
            value="tests:factory",
            load=lambda: factory,
        )
        monkeypatch.setattr(_runners, "entry_points", lambda group: [entry])
        pytester.makefile(".yaml", **{"conformance/conformance": SPEC})

    return build


def test_each_declared_scenario_becomes_a_test(pytester, scenarios) -> None:
    scenarios()

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines(
        ["*conformance.yaml::inference*", "*conformance.yaml::tool_calling*"]
    )


def test_list_entries_use_descriptions_without_merging_duplicates(
    pytester, scenarios
) -> None:
    scenarios()
    conformance = pytester.path / "conformance"
    (conformance / "contract.yaml").write_text(
        """
description: Repeated-label contract.
scenarios:
  - description: Repeated human label.
    action: {kind: first}
    expect: {}
  - description: Repeated human label.
    action: {kind: second}
    expect: {}
"""
    )
    (conformance / "conformance.yaml").write_text(
        """
runner: demo-conformance
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_run: python client.py
"""
    )

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=2)
    output = result.stdout.str()
    assert "conformance.yaml::[0] Repeated human label. PASSED" in output
    assert "conformance.yaml::[1] Repeated human label. PASSED" in output


def test_a_scenarios_failures_are_the_test_failure(
    pytester, scenarios
) -> None:
    scenarios(failing=frozenset({"inference"}))

    result = pytester.runpytest()

    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["*inference: nope*"])


def test_one_session_is_shared_by_a_directory(pytester, scenarios) -> None:
    """So a declared server and `setup` run once, not per scenario."""
    scenarios()

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)
    opened = (pytester.path / "opened.log").read_text().splitlines()
    assert len(opened) == 1, opened


def test_collection_and_execution_share_one_loaded_spec(
    pytester, scenarios, monkeypatch
) -> None:
    scenarios()
    loads: list[Path] = []
    load_spec = pytest_plugin.load_spec

    def counted_load_spec(directory: Path):
        loads.append(directory)
        return load_spec(directory)

    monkeypatch.setattr(pytest_plugin, "load_spec", counted_load_spec)

    result = pytester.runpytest()

    result.assert_outcomes(passed=2)
    assert len(loads) == 1


def test_a_broken_spec_is_a_collection_error(pytester, scenarios) -> None:
    scenarios()
    pytester.makefile(
        ".yaml",
        **{
            "conformance/conformance": "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\n"
        },
    )

    result = pytester.runpytest()

    result.stdout.fnmatch_lines(["*declares no scenarios*"])


def test_without_weaver_the_scenarios_skip(
    pytester, scenarios, monkeypatch
) -> None:
    """A machine without the binary shouldn't fail an unrelated test run."""
    scenarios()

    def missing() -> None:
        raise WeaverNotInstalledError("weaver is not on PATH")

    monkeypatch.setattr(pytest_plugin, "check_weaver", missing)

    # -rs: the skip reason says what to install, and is worth asserting.
    result = pytester.runpytest("-rs")

    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(["*weaver is not on PATH*"])
