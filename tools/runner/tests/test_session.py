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
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import opentelemetry.test.weaver_live_check as live_check
from opentelemetry.conformance import (
    SpecError,
    WeaverSpec,
    _session,
    conformance_session,
    load_spec,
)
from opentelemetry.conformance._otlp_capture import (
    CapturedExport,
    CapturedSpan,
    CapturedWindow,
    UnexpectedExportsError,
)
from opentelemetry.conformance._session import (
    ConformanceSession,
    ScenarioReport,
    _run_command,
    _start_weaver,
)
from opentelemetry.conformance._spec import ExpectedViolation, ScenarioSpec
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2

SPEC = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
  tool_calling:
    run: python tool_calling.py
"""

_new_live_check = ConformanceSession._new_live_check


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


class _LiveReport:
    def __init__(self) -> None:
        self.violations: list[dict[str, object]] = []
        self._report = {"statistics": {}, "samples": []}


class _SessionWeaver:
    instances: list[_SessionWeaver] = []

    def __init__(self) -> None:
        self.starts = 0
        self.ends = 0
        self.closes = 0
        self.otlp_endpoint = "http://weaver"
        self.report = _LiveReport()
        self.instances.append(self)

    def start(self) -> _SessionWeaver:
        self.starts += 1
        return self

    def end(self, timeout: int) -> _LiveReport:
        del timeout
        self.ends += 1
        return self.report

    def close(self) -> None:
        self.closes += 1


class _Capture:
    instances: list[_Capture] = []
    telemetry: dict[str, CapturedWindow] = {}

    def __init__(self, upstream_endpoint: str) -> None:
        self.upstream_endpoint = upstream_endpoint
        self.endpoint = "http://capture"
        self.windows: list[str] = []
        self.closed = 0
        self.calls: list[str] = []
        # What a late-admitted export leaves behind: the double reveals it
        # only once ingress is closed, so reading the quarantine first misses
        # it exactly as the transport would.
        self.late_quarantine: tuple[CapturedExport, ...] = ()
        # What a package whose telemetry cannot be stopped looks like from
        # here: the failure the session finalizes on.
        self.close_ingress_error: BaseException | None = None
        self._quarantined: tuple[CapturedExport, ...] = ()
        self.instances.append(self)

    def __enter__(self) -> _Capture:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def open_window(self, name: str) -> str:
        self.windows.append(name)
        return name

    def close_window(
        self, window: str, *, timeout: float | None = None
    ) -> CapturedWindow:
        del timeout
        return self.telemetry.get(
            window,
            CapturedWindow(
                name=window,
                generation=len(self.windows),
                exports=(),
                spans=(),
                metric_names=(),
                event_names=(),
            ),
        )

    def drain(self, *, timeout: float | None = None) -> None:
        del timeout
        self.calls.append("drain")

    def close_ingress(self, *, timeout: float | None = None) -> None:
        del timeout
        self.calls.append("close_ingress")
        if self.close_ingress_error is not None:
            raise self.close_ingress_error
        self._quarantined = self.late_quarantine

    def raise_for_quarantined(self) -> None:
        self.calls.append("raise_for_quarantined")
        if self._quarantined:
            raise UnexpectedExportsError(
                "OTLP exports arrived without an active capture window: "
                f"traces={len(self._quarantined)}"
            )

    @property
    def quarantined_requests(self) -> tuple[CapturedExport, ...]:
        self.calls.append("quarantined_requests")
        return self._quarantined

    def close(self) -> None:
        self.calls.append("close")
        self.closed += 1


@pytest.fixture(autouse=True)
def package_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    _SessionWeaver.instances.clear()
    _Capture.instances.clear()
    _Capture.telemetry.clear()
    monkeypatch.setattr(
        ConformanceSession,
        "_new_live_check",
        lambda _self: _SessionWeaver(),
    )
    monkeypatch.setattr(_session, "OtlpCaptureProxy", _Capture)


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
    assert json.loads((directory / "reports" / "weaver.json").read_text()) == {
        "samples": [],
        "statistics": {},
    }


def test_run_all_uses_one_weaver_and_one_stable_capture_endpoint(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoints: list[str] = []

    def execute(
        _self: ConformanceSession,
        _scenario: object,
        endpoint: str,
    ) -> subprocess.CompletedProcess[str]:
        endpoints.append(endpoint)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(ConformanceSession, "_execute", execute)
    opened = session(directory, tmp_path / "data.json")

    reports = opened.run_all()
    package = opened.finalize()
    assert opened.finalize() is package

    assert len(reports) == 2
    assert endpoints == ["http://capture", "http://capture"]
    assert len(_SessionWeaver.instances) == 1
    assert _SessionWeaver.instances[0].starts == 1
    assert _SessionWeaver.instances[0].ends == 1
    assert len(_Capture.instances) == 1
    assert _Capture.instances[0].windows == ["inference", "tool_calling"]


def test_run_all_batches_scenarios_that_share_a_persistent_command(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = session(directory, tmp_path / "data.json")
    command = ("controller",)
    opened._spec = replace(  # pyright: ignore[reportPrivateUsage]
        opened.spec,
        scenarios={
            name: replace(
                scenario,
                run=command,
                protocol="jsonl-v1",
                action={"name": name},
            )
            for name, scenario in opened.spec.scenarios.items()
        },
    )
    batches: list[tuple[str, ...]] = []

    def run_persistent(
        _self: ConformanceSession, scenarios: Sequence[ScenarioSpec]
    ) -> tuple[ScenarioReport, ...]:
        batches.append(tuple(scenario.name for scenario in scenarios))
        return ()

    monkeypatch.setattr(ConformanceSession, "_run_persistent", run_persistent)

    assert opened.run_all() == ()
    assert batches == [("inference", "tool_calling")]


def test_persistent_process_gets_runner_owned_export_settings(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = session(directory, tmp_path / "data.json")
    scenario = replace(
        opened.spec.scenarios["inference"],
        run=("controller",),
        protocol="jsonl-v1",
        action={"name": "inference"},
        env={
            "OTEL_BSP_SCHEDULE_DELAY": "999",
            "OTEL_METRIC_EXPORT_INTERVAL": "999",
        },
    )
    captured: dict[str, str] = {}

    class Controller:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            captured.update(cast(Mapping[str, str], kwargs["env"]))
            self.readiness = CapturedWindow("readiness", 0, (), (), (), ())

        def run(self) -> tuple[()]:
            return ()

    monkeypatch.setattr(_session, "PersistentController", Controller)

    assert opened._run_persistent((scenario,)) == ()
    assert captured["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://capture"
    assert captured["OTEL_BSP_SCHEDULE_DELAY"] == "50"
    assert captured["OTEL_BLRP_SCHEDULE_DELAY"] == "50"
    assert captured["OTEL_METRIC_EXPORT_INTERVAL"] == "100"
    assert (
        captured["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"]
        == "delta"
    )


def test_finalize_reads_the_quarantine_only_after_ingress_closes(
    directory: Path, tmp_path: Path
) -> None:
    """An export admitted at the boundary is still validated.

    The double reveals a quarantined export the moment ingress closes, which
    is where a call the transport had already accepted lands. Reading the
    quarantine before that would let it escape every check and every report.
    """
    opened = session(directory, tmp_path / "data.json")
    opened.start()
    capture = _Capture.instances[0]
    capture.late_quarantine = (
        CapturedExport(
            signal="traces",
            request=trace_service_pb2.ExportTraceServiceRequest(),
        ),
    )

    package = opened.finalize()

    assert capture.calls[:3] == [
        "close_ingress",
        "raise_for_quarantined",
        "quarantined_requests",
    ]
    assert package.failures == [
        "OTLP exports arrived without an active capture window: traces=1"
    ]
    assert (directory / "reports" / "unwindowed.json").is_file()


def test_a_failed_finalize_is_raised_to_callers_but_not_to_teardown(
    directory: Path, tmp_path: Path
) -> None:
    """The failure belongs to whoever asked for the report, once.

    A caller asking again for a report the session could not produce gets the
    same failure rather than a second attempt at telemetry that is already
    gone. Closing the session is not such a caller: raising there would put
    the failure a run has already reported on top of that run's own result.
    """

    opened = session(directory, tmp_path / "data.json")
    opened.start()
    capture = _Capture.instances[0]
    error = RuntimeError("ingress would not close")
    capture.close_ingress_error = error

    with pytest.raises(RuntimeError) as first:
        opened.finalize()
    with pytest.raises(RuntimeError) as again:
        opened.finalize()

    assert first.value is error
    assert again.value is error
    # Released where it failed, and released once.
    assert capture.closed == 1
    assert _SessionWeaver.instances[0].closes == 1

    opened.__exit__(None, None, None)

    assert capture.closed == 1
    assert _SessionWeaver.instances[0].closes == 1
    assert capture.calls.count("close_ingress") == 1


def test_persistent_process_gets_the_runner_owned_action_table(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A driver is told the table, so it never rebuilds its own."""
    opened = session(directory, tmp_path / "data.json")
    table = ({"request": {"path": "/health"}}, {"request": {"path": "/one"}})
    opened._spec = replace(  # pyright: ignore[reportPrivateUsage]
        opened.spec, action_table=table
    )
    scenario = replace(
        opened.spec.scenarios["inference"],
        run=("controller",),
        protocol="jsonl-v1",
        action={"request": {"path": "/one"}},
    )
    captured: dict[str, str] = {}

    class Controller:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            captured.update(cast(Mapping[str, str], kwargs["env"]))
            self.readiness = CapturedWindow("readiness", 0, (), (), (), ())

        def run(self) -> tuple[()]:
            return ()

    monkeypatch.setattr(_session, "PersistentController", Controller)

    assert opened._run_persistent((scenario,)) == ()
    assert json.loads(captured["OTEL_CONFORMANCE_SCENARIO_ACTIONS"]) == [
        {"request": {"path": "/health"}},
        {"request": {"path": "/one"}},
    ]


def test_run_checks_scenario_against_its_captured_window(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (directory / "conformance.yaml").write_text(
        """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
    spans:
      - match:
          attributes: {gen_ai.operation.name: chat}
        expect: {count: 1}
    metrics: [gen_ai.client.operation.duration]
    events: [gen_ai.client.inference.operation.details]
"""
    )
    _Capture.telemetry["inference"] = CapturedWindow(
        name="inference",
        generation=1,
        exports=(),
        spans=(
            CapturedSpan(
                name="chat model",
                kind="SPAN_KIND_CLIENT",
                attributes={"gen_ai.operation.name": "chat"},
                trace_id=b"\x01" * 16,
                span_id=b"\x02" * 8,
                parent_span_id=b"",
                start_time_unix_nano=1,
                end_time_unix_nano=2,
            ),
        ),
        metric_names=("gen_ai.client.operation.duration",),
        event_names=("gen_ai.client.inference.operation.details",),
    )
    monkeypatch.setattr(
        ConformanceSession,
        "_execute",
        lambda *_args: subprocess.CompletedProcess([], 0, "", ""),
    )

    report = session(directory, tmp_path / "data.json").run("inference")

    assert report.failures == []
    assert report.telemetry is _Capture.telemetry["inference"]


def test_complete_run_reports_stale_package_declaration(
    directory: Path, tmp_path: Path
) -> None:
    declared = ExpectedViolation(
        id="missing_attribute", context=None, reason="known gap"
    )
    opened = session(directory, tmp_path / "data.json")
    opened._spec = replace(  # pyright: ignore[reportPrivateUsage]
        opened.spec, expected_violations=(declared,)
    )
    opened._ran.update(opened.spec.scenarios)  # pyright: ignore[reportPrivateUsage]

    package = opened.finalize()

    assert len(package.failures) == 1
    assert "no longer reported" in package.failures[0]


def test_partial_run_skips_stale_declarations_but_reports_unexpected_findings(
    directory: Path, tmp_path: Path
) -> None:
    declared = ExpectedViolation(
        id="declared", context=None, reason="known gap"
    )
    opened = session(directory, tmp_path / "data.json")
    opened._spec = replace(  # pyright: ignore[reportPrivateUsage]
        opened.spec, expected_violations=(declared,)
    )
    opened._ran.add("inference")  # pyright: ignore[reportPrivateUsage]
    opened.start()
    _SessionWeaver.instances[0].report.violations.append(
        {"id": "unexpected", "message": "bad telemetry"}
    )

    package = opened.finalize()

    assert package.failures == []
    assert package.violations == ["[unexpected] bad telemetry"]


def test_weaver_inactivity_timeout_is_disabled_for_the_package(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, object] = {}

    def weaver(**kwargs: object) -> _SessionWeaver:
        options.update(kwargs)
        return _SessionWeaver()

    monkeypatch.setattr(live_check, "WeaverLiveCheck", weaver)

    _new_live_check(session(directory, tmp_path / "data.json"))

    assert options["inactivity_timeout"] == 0


def test_setup_precedes_package_telemetry_start(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(_session, "check_weaver", lambda: None)
    monkeypatch.setattr(
        ConformanceSession,
        "setup",
        lambda _self: events.append("setup"),
    )

    def weaver() -> _SessionWeaver:
        events.append("weaver")
        return _SessionWeaver()

    monkeypatch.setattr(
        ConformanceSession, "_new_live_check", lambda _: weaver()
    )

    with conformance_session(
        directory,
        data_file=tmp_path / "data.json",
        weaver=WeaverSpec(registry="model"),
    ):
        events.append("opened")

    assert events == ["setup", "weaver", "opened"]


def test_exception_closes_package_telemetry_without_reducing(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_file = tmp_path / "data.json"

    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("runner broke")

    monkeypatch.setattr(ConformanceSession, "_execute", broken)

    with pytest.raises(RuntimeError, match="runner broke"):
        with session(directory, data_file) as opened:
            opened.run("inference")

    assert _SessionWeaver.instances[0].ends == 0
    assert _SessionWeaver.instances[0].closes == 1
    assert not data_file.exists()


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


def test_contract_selection_is_injected_into_the_one_shot_process(
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
        action={"z": [2, 1], "a": {"method": "GET"}},
    )

    opened._execute(scenario, "http://collector")

    assert captured["OTEL_CONFORMANCE_SCENARIO_INDEX"] == "3"
    assert captured["OTEL_CONFORMANCE_SCENARIO_ACTION"] == (
        '{"a":{"method":"GET"},"z":[2,1]}'
    )


def test_persistent_scenario_protocol_does_not_use_one_shot_execution(
    directory: Path,
    tmp_path: Path,
) -> None:
    opened = session(directory, tmp_path / "data.json")
    scenario = replace(
        opened.spec.scenarios["inference"],
        run=("controller",),
        protocol="jsonl-v1",
        action={"method": "GET"},
    )

    with pytest.raises(RuntimeError, match="not a one-shot"):
        opened._execute(scenario, "http://collector")


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


def test_a_scenario_replaces_only_its_own_capture(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running one scenario mustn't discard what the others last reported."""
    reports = tmp_path / "reports"
    captures = reports / "scenarios"
    captures.mkdir(parents=True)
    (captures / "inference.json").write_text('{"run": "first"}')
    (captures / "tool_calling.json").write_text('{"run": "first"}')
    monkeypatch.setattr(
        ConformanceSession,
        "_execute",
        lambda *_args: subprocess.CompletedProcess([], 0, "", ""),
    )

    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened.run("inference")

    assert json.loads((captures / "inference.json").read_text())["format"] == (
        "opentelemetry-conformance-capture/v1"
    )
    assert json.loads((captures / "tool_calling.json").read_text()) == {
        "run": "first"
    }


def test_a_complete_run_cleans_owned_stale_reports_only(
    directory: Path, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    captures = reports / "scenarios"
    captures.mkdir()
    stale_capture = captures / "deleted.json"
    stale_capture.write_text("{}")
    (reports / "inference.json").write_text("{}")
    unrelated = reports / "metadata.json"
    unrelated.write_text('{"samples": [], "statistics": {}}')
    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened._ran.update(opened.spec.scenarios)

    opened.close()

    assert not (reports / "inference.json").exists()
    assert not stale_capture.exists()
    assert unrelated.exists()


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
