# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Collecting ``conformance.yaml`` as a test file.

A scenario directory already declares everything a test needs, so no repo
should have to write a module that points at it. These run pytest inside
pytest, with a stub factory standing in for a real session — starting weaver
is the session's job, not the plugin's.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from opentelemetry.conformance import (
    CapturedWindow,
    PackageReport,
    ScenarioReport,
    WeaverNotInstalledError,
    WeaverSpec,
    _runners,
    pytest_plugin,
)
from opentelemetry.conformance._session import ConformanceSession
from opentelemetry.conformance._spec import PackageSpec

pytest_plugins = ["pytester"]

EMPTY_WINDOW = CapturedWindow(
    name="test",
    generation=1,
    exports=(),
    spans=(),
    metric_names=(),
    event_names=(),
)

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

    def __init__(
        self,
        failing: frozenset[str],
        package_failures: tuple[str, ...],
        package_violations: tuple[str, ...],
    ) -> None:
        self._failing = failing
        self._package_failures = package_failures
        self._package_violations = package_violations
        self._reports: tuple[ScenarioReport, ...] = ()

    def run_all(self) -> tuple[ScenarioReport, ...]:
        self._reports = tuple(
            ScenarioReport(
                name=name,
                failures=[f"{name}: nope"] if name in self._failing else [],
                telemetry=EMPTY_WINDOW,
            )
            for name in ("inference", "tool_calling")
        )
        return self._reports

    def finalize(self) -> PackageReport:
        return PackageReport(
            scenarios=self._reports,
            failures=list(self._package_failures),
            violations=list(self._package_violations),
            report=SimpleNamespace(violations=[]),
        )


@pytest.fixture(name="scenarios")
def _scenarios(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch):
    """A scenario directory, with a stub wrapper registered for its ``runner:``.

    ``pytester`` runs the inner pytest in this process, so both patches reach
    it — and both are undone afterwards, which registering the stub from a
    generated conftest would not be.
    """
    monkeypatch.setattr(pytest_plugin, "check_weaver", lambda: None)

    def build(
        failing: frozenset[str] = frozenset(),
        package_failures: tuple[str, ...] = (),
        package_violations: tuple[str, ...] = (),
    ) -> None:
        @contextmanager
        def factory(directory: Path, **_kwargs: object):
            # Where the session was opened, for the test that counts them.
            with Path("opened.log").open("a") as log:
                log.write(f"{directory}\n")
            yield FakeSession(failing, package_failures, package_violations)

        entry = SimpleNamespace(
            name="demo-conformance",
            value="tests:factory",
            load=lambda: factory,
        )
        monkeypatch.setattr(_runners, "entry_points", lambda group: [entry])
        pytester.makefile(".yaml", **{"conformance/conformance": SPEC})

    return build


def test_each_package_becomes_one_atomic_test(pytester, scenarios) -> None:
    scenarios()

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*conformance.yaml::package*"])


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

    result.assert_outcomes(passed=1)
    output = result.stdout.str()
    assert "conformance.yaml::package PASSED" in output


def test_a_scenarios_failures_are_the_test_failure(
    pytester, scenarios
) -> None:
    scenarios(failing=frozenset({"inference"}))

    result = pytester.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*inference: nope*"])


def test_a_package_failure_is_the_test_failure(pytester, scenarios) -> None:
    scenarios(package_failures=("[missing] no longer reported",))

    result = pytester.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*missing*no longer reported*"])


def test_a_package_violation_is_the_test_failure(pytester, scenarios) -> None:
    scenarios(package_violations=("[unexpected] bad telemetry",))

    result = pytester.runpytest()

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*unexpected*bad telemetry*"])


def test_one_session_is_shared_by_a_directory(pytester, scenarios) -> None:
    """So a declared server and `setup` run once, not per scenario."""
    scenarios()

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
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

    result.assert_outcomes(passed=1)
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

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*weaver is not on PATH*"])


class _BrokenCapture:
    """A capture that cannot be stopped, which is what fails a finalize."""

    endpoint = "http://capture"

    def close_ingress(self, *, timeout: float | None = None) -> None:
        del timeout
        raise RuntimeError("capture drain failed")


def _record_release() -> None:
    """What the session held, written down where a test can read it."""
    with Path("released.log").open("a") as log:
        log.write("released\n")


class _FinalizeFails(ConformanceSession):
    """A real session whose package telemetry fails to stop.

    Only the session decides what closing it a second time does, so what the
    plugin's teardown closes has to be a real one for the answer to mean
    anything. Weaver and the capture proxy are stubbed because starting them
    is not what this is about.
    """

    def run_all(
        self, selected_names: object = None
    ) -> tuple[ScenarioReport, ...]:
        del selected_names
        return ()

    def start(self) -> None:
        if self._resources is not None:
            return
        resources = ExitStack()
        resources.callback(_record_release)
        self._resources = resources
        self._capture = cast(Any, _BrokenCapture())
        self._live_check = cast(Any, SimpleNamespace(end=lambda timeout: None))


def test_a_failed_finalize_fails_the_test_and_teardown_stays_quiet(
    pytester, monkeypatch
) -> None:
    """The run ends on the failure it collected, not on a copy of it.

    ``runtest`` finalizes the package, so a finalize that fails is the test's
    own failure. Closing the session afterwards releases what it still holds;
    raising the same failure again there would come out of
    ``pytest_unconfigure``, after the report the run is judged on.
    """

    monkeypatch.setattr(pytest_plugin, "check_weaver", lambda: None)

    @contextmanager
    def factory(directory: Path, *, spec: PackageSpec, **_kwargs: object):
        session = _FinalizeFails(
            spec,
            directory / "reports",
            variables={},
            weaver=WeaverSpec(registry="model"),
            env={},
            data_file=directory / "data.json",
            build_data=lambda reports, spec: {},
        )
        with session:
            yield session

    entry = SimpleNamespace(
        name="demo-conformance",
        value="tests:factory",
        load=lambda: factory,
    )
    monkeypatch.setattr(_runners, "entry_points", lambda group: [entry])
    pytester.makefile(".yaml", **{"conformance/conformance": SPEC})

    result = pytester.runpytest()

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(failed=1)
    output = result.stdout.str() + result.stderr.str()
    assert "capture drain failed" in output
    assert "INTERNALERROR" not in output
    released = (pytester.path / "released.log").read_text().splitlines()
    assert released == ["released"]
