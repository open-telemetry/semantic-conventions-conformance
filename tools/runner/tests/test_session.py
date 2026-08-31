# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The session around a run: commands, ``setup``, and the data file.

A command the package got wrong is a failed scenario, not an exception, so
one bad ``run:`` entry doesn't take the whole run down with it. Running a
scenario needs weaver, so the tests that don't exercise it drive the session
directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentelemetry.conformance import (
    SpecError,
    WeaverSpec,
    _session,
    conformance_session,
    load_spec,
)
from opentelemetry.conformance._session import (
    ConformanceSession,
    _run_command,
    _start_weaver,
)
from opentelemetry.conformance._spec import (
    AttributeMatcher,
    ScenarioSpec,
    SpanExpectation,
    SpanMatch,
)

SPEC = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
  tool_calling:
    run: python tool_calling.py
"""


def test_a_command_that_runs(tmp_path: Path) -> None:
    completed = _run_command(
        (sys.executable, "-c", "print('hello')"), cwd=tmp_path, env={}
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"


def test_a_command_that_does_not_exist(tmp_path: Path) -> None:
    completed = _run_command(
        ("definitely-not-a-command", "--flag"), cwd=tmp_path, env={}
    )

    assert completed.returncode == 1
    assert "definitely-not-a-command --flag" in completed.stderr


def test_a_command_that_overruns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", "0.5")

    completed = _run_command(
        (sys.executable, "-c", "import time; time.sleep(30)"),
        cwd=tmp_path,
        env={},
    )

    assert completed.returncode == 1
    assert "did not finish within" in completed.stderr


def test_weaver_startup_retries_after_a_timeout() -> None:
    attempts: list[_FakeWeaver] = []

    def factory() -> _FakeWeaver:
        weaver = _FakeWeaver(fail_start=not attempts)
        attempts.append(weaver)
        return weaver

    with _start_weaver(factory) as weaver:
        assert weaver is attempts[1]

    assert [attempt.starts for attempt in attempts] == [1, 1]
    assert [attempt.closes for attempt in attempts] == [1, 1]


def test_weaver_startup_stops_after_the_retry() -> None:
    attempts: list[_FakeWeaver] = []

    def factory() -> _FakeWeaver:
        weaver = _FakeWeaver(fail_start=True)
        attempts.append(weaver)
        return weaver

    with pytest.raises(TimeoutError), _start_weaver(factory):
        pass

    assert len(attempts) == 2
    assert [attempt.closes for attempt in attempts] == [1, 1]


class _FakeWeaver:
    def __init__(self, *, fail_start: bool) -> None:
        self.fail_start = fail_start
        self.starts = 0
        self.closes = 0

    def start(self) -> _FakeWeaver:
        self.starts += 1
        if self.fail_start:
            raise TimeoutError
        return self

    def close(self) -> None:
        self.closes += 1


def test_the_scenario_gets_exactly_the_environment_it_was_given(
    tmp_path: Path,
) -> None:
    completed = _run_command(
        (sys.executable, "-c", "import os; print(os.environ['DECLARED'])"),
        cwd=tmp_path,
        env={"DECLARED": "value"},
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "value"


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    (tmp_path / "conformance.yaml").write_text(SPEC)
    return tmp_path


def session(
    directory: Path,
    data_file: Path,
    setup: tuple[str, ...] | None = None,
    report_dir: Path | None = None,
) -> ConformanceSession:
    return ConformanceSession(
        replace(load_spec(directory), setup=setup),
        report_dir if report_dir is not None else directory / "reports",
        variables={"ROOT": str(directory)},
        weaver=WeaverSpec(registry="model"),
        env={},
        data_file=data_file,
        build_data=lambda reports, spec: {
            "library": spec.instrumented_library,
            "reports": reports.name,
        },
    )


def test_a_complete_run_writes_the_data_file(
    directory: Path, tmp_path: Path
) -> None:
    data_file = tmp_path / "nested" / "data.json"
    opened = session(directory, data_file)
    opened._ran.update(["inference", "tool_calling"])

    opened.close()

    assert json.loads(data_file.read_text()) == {
        "library": "demo",
        "reports": "reports",
    }


def test_a_filtered_run_leaves_the_data_file_alone(
    directory: Path, tmp_path: Path
) -> None:
    """A reduction over the reports only holds across a whole run."""
    data_file = tmp_path / "data.json"
    opened = session(directory, data_file)
    opened._ran.add("inference")

    opened.close()

    assert not data_file.exists()


def test_a_run_that_raised_leaves_the_data_file_alone(
    directory: Path, tmp_path: Path
) -> None:
    """Its reports cover part of a run; reducing them would commit a half-run."""
    data_file = tmp_path / "data.json"

    with pytest.raises(RuntimeError, match="harness"):
        with session(directory, data_file) as opened:
            opened._ran.update(["inference", "tool_calling"])
            raise RuntimeError("the harness broke")

    assert not data_file.exists()


def test_a_run_whose_scenarios_failed_still_writes_the_data_file(
    directory: Path, tmp_path: Path
) -> None:
    """A violation is the result, not an error — the run still reduces."""
    data_file = tmp_path / "data.json"

    with session(directory, data_file) as opened:
        opened._ran.update(["inference", "tool_calling"])

    assert json.loads(data_file.read_text()) == {
        "library": "demo",
        "reports": "reports",
    }


def test_setup_is_optional(directory: Path, tmp_path: Path) -> None:
    assert session(directory, tmp_path / "data.json").setup() is None


def test_setup_runs_the_declared_command(
    directory: Path, tmp_path: Path
) -> None:
    completed = session(
        directory,
        tmp_path / "data.json",
        setup=(sys.executable, "-c", "print('prepared')"),
    ).setup()

    assert completed is not None
    assert completed.stdout.strip() == "prepared"


def test_a_failing_setup_stops_the_session(
    directory: Path, tmp_path: Path
) -> None:
    opened = session(
        directory,
        tmp_path / "data.json",
        setup=(sys.executable, "-c", "raise SystemExit(3)"),
    )

    with pytest.raises(RuntimeError, match="setup command"):
        opened.setup()


def test_declared_paths_resolve_against_the_package(
    directory: Path, tmp_path: Path
) -> None:
    """A path in a config file reads as relative to that file."""
    opened = session(directory, tmp_path / "data.json")

    # Use tmp_path's anchor so Path.is_absolute() recognizes this on Windows;
    # a rooted path without a drive is not absolute to pathlib.
    absolute = str(Path(tmp_path.anchor) / "absolute" / "model")

    assert opened._resolve_path("model") == str(directory / "model")
    assert opened._resolve_path("${ROOT}/model") == str(directory / "model")
    assert opened._resolve_path(absolute) == absolute


def test_runtime_variables_are_resolved_in_span_expectations(
    directory: Path, tmp_path: Path
) -> None:
    opened = session(directory, tmp_path / "data.json")
    spec = ScenarioSpec(
        name="0000",
        directory=directory,
        env={},
        run=("run",),
        spans=(
            SpanExpectation(
                match=SpanMatch(attributes={"url.full": "${ROOT}/one"}),
                count=1,
                attributes={
                    "server.address": AttributeMatcher(equals="${ROOT}")
                },
            ),
        ),
        metrics=None,
        events=None,
        expected_violations=(),
        description="Sends one request.",
        index=0,
    )

    resolved = opened._resolve_expectations(spec)

    assert resolved.spans is not None
    assert resolved.spans[0].match.attributes == {
        "url.full": f"{directory}/one"
    }
    assert resolved.spans[0].attributes["server.address"].equals == str(
        directory
    )


def test_unknown_runtime_expectation_variable_is_rejected(
    directory: Path, tmp_path: Path
) -> None:
    opened = session(directory, tmp_path / "data.json")
    spec = ScenarioSpec(
        name="0000",
        directory=directory,
        env={},
        run=("run",),
        spans=(
            SpanExpectation(
                match=SpanMatch(attributes={"url.full": "${MISSING}"}),
                count=1,
            ),
        ),
        metrics=None,
        events=None,
        expected_violations=(),
        description="Sends one request.",
    )

    with pytest.raises(SpecError, match="MISSING"):
        opened._resolve_expectations(spec)


def test_contract_index_is_injected_into_the_scenario_process(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def run(
        command: tuple[str, ...], *, cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        del command, cwd
        captured.update(env)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(_session, "_run_command", run)
    opened = session(directory, tmp_path / "data.json")
    scenario = replace(
        opened.spec.scenarios["inference"],
        index=3,
    )

    opened._execute(scenario, "http://collector")

    assert captured["OTEL_CONFORMANCE_SCENARIO_INDEX"] == "3"


def test_a_missing_registry_is_a_spec_error(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Opening a session looks for weaver before it reads the registry, and
    # this is the one test here that goes in through the front door.
    monkeypatch.setattr(_session, "check_weaver", lambda: None)
    with pytest.raises(SpecError, match="no weaver registry"):
        with conformance_session(directory):
            pass


def test_a_preloaded_spec_is_not_read_again(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = load_spec(directory)
    monkeypatch.setattr(_session, "check_weaver", lambda: None)
    monkeypatch.setattr(
        _session,
        "load_spec",
        lambda path: pytest.fail(f"reloaded {path}"),
    )

    with conformance_session(
        directory,
        data_file=tmp_path / "data.json",
        weaver=WeaverSpec(registry="model"),
        spec=spec,
    ) as opened:
        assert opened.spec is spec


def test_a_scenario_replaces_only_its_own_report(
    directory: Path, tmp_path: Path
) -> None:
    """Running one scenario mustn't discard what the others last reported."""
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "inference.json").write_text('{"run": "first"}')
    (reports / "tool_calling.json").write_text('{"run": "first"}')

    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened._dump("inference", SimpleNamespace(_report={"run": "second"}))

    assert json.loads((reports / "inference.json").read_text()) == {
        "run": "second"
    }
    assert json.loads((reports / "tool_calling.json").read_text()) == {
        "run": "first"
    }


def test_a_complete_run_removes_reports_for_deleted_scenarios(
    directory: Path, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "inference.json").write_text("{}")
    (reports / "tool_calling.json").write_text("{}")
    stale = reports / "deleted.json"
    stale.write_text("{}")
    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened._ran.update(opened.spec.scenarios)

    opened.close()

    assert not stale.exists()


def test_reports_default_to_inside_the_scenario_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sibling implementations run the same scenario names; keep them apart."""
    monkeypatch.chdir(tmp_path)
    scenarios = Path("gen-ai/python/openai/opentelemetry")

    assert (
        _session._default_report_dir(scenarios)
        == scenarios / _session.DEFAULT_REPORT_DIR
    )


def test_the_default_report_dir_does_not_move_with_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pytest and a shell pick different ones; the reports land in one place."""
    scenarios = tmp_path / "gen-ai" / "python" / "openai" / "opentelemetry"
    scenarios.mkdir(parents=True)
    here = tmp_path / "here"
    here.mkdir()

    monkeypatch.chdir(tmp_path)
    from_root = _session._default_report_dir(scenarios)
    monkeypatch.chdir(here)

    assert _session._default_report_dir(scenarios) == from_root
