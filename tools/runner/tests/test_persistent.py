# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The jsonl-v1 persistent execution controller."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Condition, Event, Thread
from types import SimpleNamespace
from typing import cast

import pytest

from opentelemetry.conformance._otlp_capture import (
    CapturedExport,
    CaptureSnapshot,
    CaptureWindow,
    OtlpCaptureProxy,
    decode_window,
)
from opentelemetry.conformance._persistent import (
    _IN_FLIGHT_WAIT_SECONDS,
    DEFAULT_SETTLE_DELAY,
    ActionState,
    PersistentController,
    PersistentProtocolError,
    _ActionWindow,
    _Message,
    partition_persistent_exports,
)
from opentelemetry.conformance._spec import (
    ScenarioSpec,
    SpanExpectation,
    SpanMatch,
)
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2
from opentelemetry.proto.trace.v1 import trace_pb2


class _Capture:
    def __init__(
        self,
        exports: tuple[CapturedExport, ...] = (),
        on_drain=None,
        on_snapshot=None,
        after_snapshot=None,
        in_flight: int = 0,
    ) -> None:
        self.exports = exports
        self.window: CaptureWindow | None = None
        self.notifier = None
        self.on_drain = on_drain
        self.on_snapshot = on_snapshot
        # Runs once the snapshot has been taken, so what it adds is a change
        # the controller has already read past — where a real export landing
        # between the snapshot and the wait puts it.
        self.after_snapshot = after_snapshot
        # What the capture is still carrying towards its upstream, which is
        # what a window may not be sealed on top of.
        self.in_flight = in_flight
        self.snapshot_calls = 0

    def open_window(self, name: str) -> CaptureWindow:
        self.window = CaptureWindow(name, 1)
        return self.window

    def set_change_notifier(self, notifier: object) -> None:
        self.notifier = notifier

    def snapshot(self, window: CaptureWindow) -> CaptureSnapshot:
        assert window is self.window
        self.snapshot_calls += 1
        if self.on_snapshot is not None:
            self.on_snapshot(self)
        taken = CaptureSnapshot(
            self.exports, self.in_flight, len(self.exports)
        )
        if self.after_snapshot is not None:
            self.after_snapshot(self)
        return taken

    def announce(self) -> None:
        """Report a change the way the real capture does."""
        notifier = self.notifier
        assert notifier is not None
        cast(Callable[[], None], notifier)()

    def drain(self, *, timeout: float | None = None) -> None:
        del timeout
        if self.on_drain is not None:
            self.on_drain(self)

    def close_window(
        self, window: CaptureWindow, *, timeout: float | None = None
    ):
        del timeout
        return decode_window(window, self.exports)

    def requests(self, window: CaptureWindow) -> tuple[CapturedExport, ...]:
        assert window is self.window
        return self.exports


def _scenario(command: tuple[str, ...], name: str = "first") -> ScenarioSpec:
    return ScenarioSpec(
        name=name,
        directory=Path.cwd(),
        env={},
        run=command,
        spans=None,
        metrics=None,
        events=None,
        action={"request": name},
        protocol="jsonl-v1",
    )


def _driver(tmp_path: Path, body: str) -> tuple[str, ...]:
    path = tmp_path / "driver.py"
    path.write_text(body, encoding="utf-8")
    return (sys.executable, "-u", str(path))


def _run(
    tmp_path: Path,
    body: str,
    *,
    count: int = 1,
    timeout: float = 1.0,
):
    command = _driver(tmp_path, body)
    scenarios = tuple(
        _scenario(command, f"action-{index}") for index in range(count)
    )
    return PersistentController(
        scenarios,
        capture=cast(OtlpCaptureProxy, _Capture()),
        cwd=tmp_path,
        env=os.environ,
        timeout=timeout,
        settle_delay=0.001,
    ).run()


_SUCCESS_DRIVER = """
import json, sys, time
print(json.dumps({"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
last = 0
for line in sys.stdin:
    action = json.loads(line)
    last = action["sequence"]
    print(json.dumps({"version": "jsonl-v1", "type": "action_complete", "sequence": last, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
print(json.dumps({"version": "jsonl-v1", "type": "stopped", "sequence": last + 1}), flush=True)
"""


def test_controller_reuses_process_and_seals_each_action(
    tmp_path: Path,
) -> None:
    results = _run(tmp_path, _SUCCESS_DRIVER, count=5)

    assert [result.state for result in results] == [ActionState.SEALED] * 5
    assert all(
        result.transitions
        == (
            ActionState.OPEN,
            ActionState.RESPONSE_COMPLETE,
            ActionState.PROVISIONALLY_SATISFIED,
            ActionState.SETTLING,
            ActionState.SEALED,
        )
        for result in results
    )
    assert len({result.trace_id for result in results}) == 5
    assert all(
        len(result.trace_id) == 32
        and int(result.trace_id, 16) != 0
        and not result.failure
        for result in results
    )


def test_final_shutdown_telemetry_is_reconciled(tmp_path: Path) -> None:
    trace_file = tmp_path / "trace-id"
    command = _driver(
        tmp_path,
        f"""
import json, sys, time
print(json.dumps({{"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
action = json.loads(sys.stdin.readline())
open({str(trace_file)!r}, "w").write(action["correlation_trace_id"])
print(json.dumps({{"version": "jsonl-v1", "type": "action_complete", "sequence": 1, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
sys.stdin.read()
print(json.dumps({{"version": "jsonl-v1", "type": "stopped", "sequence": 2}}), flush=True)
""",
    )

    def emit_at_shutdown(capture: _Capture) -> None:
        trace_id = trace_file.read_text()
        now = time.time_ns()
        capture.exports = (_trace(trace_id, now, now + 1),)

    capture = _Capture(on_drain=emit_at_shutdown)
    (result,) = PersistentController(
        (_scenario(command),),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=1.0,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert [span.trace_id.hex() for span in result.telemetry.spans] == [
        result.trace_id
    ]


@pytest.mark.parametrize(
    "record, match",
    [
        ('{"version":"jsonl-v1","type":"ready","sequence":2}', "sequence"),
        ("not json", "malformed"),
        ('{"version":"other","type":"ready","sequence":0}', "version"),
    ],
)
def test_invalid_initial_record_aborts_batch(
    tmp_path: Path, record: str, match: str
) -> None:
    body = f"print({record!r}, flush=True)\ninput()\n"

    results = _run(tmp_path, body, count=2)

    assert match in (results[0].failure or "")
    assert not results[0].executed
    assert "unexecuted" in (results[1].failure or "")


def test_action_error_aborts_remaining_actions(tmp_path: Path) -> None:
    body = """
import json, sys, time
print(json.dumps({"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
json.loads(sys.stdin.readline())
print("driver diagnostic", file=sys.stderr, flush=True)
print(json.dumps({"version": "jsonl-v1", "type": "action_error", "sequence": 1, "error": "broken"}), flush=True)
sys.stdin.read()
"""

    results = _run(tmp_path, body, count=2)

    assert "broken" in (results[0].failure or "")
    assert "driver diagnostic" in (results[0].failure or "")
    assert results[0].stderr == "driver diagnostic\n"
    assert results[0].executed
    assert not results[1].executed
    assert "unexecuted" in (results[1].failure or "")


def test_out_of_sequence_action_response_aborts_batch(tmp_path: Path) -> None:
    body = """
import json, sys, time
print(json.dumps({"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
json.loads(sys.stdin.readline())
print(json.dumps({"version": "jsonl-v1", "type": "action_complete", "sequence": 2}), flush=True)
sys.stdin.read()
"""

    results = _run(tmp_path, body, count=2)

    assert "expected sequence 1" in (results[0].failure or "")
    assert "unexecuted" in (results[1].failure or "")


def test_early_exit_and_timeout_fail_closed(tmp_path: Path) -> None:
    early = _run(tmp_path, "raise SystemExit(7)\n", count=2)
    assert "exited early with 7" in (early[0].failure or "")
    assert "unexecuted" in (early[1].failure or "")

    timed_out = _run(
        tmp_path,
        "import time\ntime.sleep(10)\n",
        count=2,
        timeout=0.02,
    )
    assert "timed out waiting for ready" in (timed_out[0].failure or "")
    assert "unexecuted" in (timed_out[1].failure or "")


def _clock() -> Callable[[], int]:
    """Strictly increasing wall-clock nanoseconds.

    Windows reports the wall clock in coarse ticks, so a fake that exports
    several intervals in one test would otherwise stamp them all alike.
    """
    last = 0

    def tick() -> int:
        nonlocal last
        last = max(time.time_ns(), last + 1)
        return last

    return tick


def _window(
    name: str, sequence: int, trace_id: str, start: int
) -> _ActionWindow:
    return _ActionWindow(
        scenario=_scenario(("driver",), name),
        sequence=sequence,
        trace_id=trace_id,
        state=ActionState.SEALED,
        sent_unix_nano=start,
        response_unix_nano=start + 10,
        sealed_unix_nano=start + 20,
    )


def _trace(trace_id: str, start: int, end: int) -> CapturedExport:
    return CapturedExport(
        "traces",
        trace_service_pb2.ExportTraceServiceRequest(
            resource_spans=[
                trace_pb2.ResourceSpans(
                    scope_spans=[
                        trace_pb2.ScopeSpans(
                            spans=[
                                trace_pb2.Span(
                                    name=trace_id[-4:],
                                    trace_id=bytes.fromhex(trace_id),
                                    span_id=b"\x01" * 8,
                                    start_time_unix_nano=start,
                                    end_time_unix_nano=end,
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
    )


def _metric(
    start: int,
    end: int,
    temporality: int = metrics_pb2.AGGREGATION_TEMPORALITY_DELTA,
    *,
    name: str = "requests",
    received: int = 0,
    monotonic: bool = True,
    scope: str = "test",
) -> CapturedExport:
    return CapturedExport(
        "metrics",
        metrics_service_pb2.ExportMetricsServiceRequest(
            resource_metrics=[
                metrics_pb2.ResourceMetrics(
                    scope_metrics=[
                        metrics_pb2.ScopeMetrics(
                            scope=common_pb2.InstrumentationScope(
                                name=scope
                            ),
                            metrics=[
                                metrics_pb2.Metric(
                                    name=name,
                                    sum=metrics_pb2.Sum(
                                        aggregation_temporality=temporality,
                                        is_monotonic=monotonic,
                                        data_points=[
                                            metrics_pb2.NumberDataPoint(
                                                start_time_unix_nano=start,
                                                time_unix_nano=end,
                                                as_int=1,
                                            )
                                        ],
                                    ),
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
        received_unix_nano=received,
    )


def test_late_trace_is_reconciled_to_its_correlation_window() -> None:
    first_id = "01" * 16
    second_id = "02" * 16
    actions = (
        _window("first", 1, first_id, 100),
        _window("second", 2, second_id, 200),
    )

    partition = partition_persistent_exports(
        (
            _trace(second_id, 210, 220),
            _trace(first_id, 110, 120),
        ),
        actions,
        300,
    )

    assert [span.name for span in partition.windows[0].spans] == [
        first_id[-4:]
    ]
    assert [span.name for span in partition.windows[1].spans] == [
        second_id[-4:]
    ]


def test_post_response_delta_boundary_seals_action(tmp_path: Path) -> None:
    action_complete = tmp_path / "action-complete"
    command = _driver(
        tmp_path,
        f"""
import json, pathlib, sys, time
print(json.dumps({{"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
json.loads(sys.stdin.readline())
pathlib.Path({str(action_complete)!r}).write_text("done")
print(json.dumps({{"version": "jsonl-v1", "type": "action_complete", "sequence": 1, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
sys.stdin.read()
print(json.dumps({{"version": "jsonl-v1", "type": "stopped", "sequence": 2}}), flush=True)
""",
    )
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )
    tick = _clock()

    def emit_boundaries(capture: _Capture) -> None:
        if not capture.exports:
            now = tick()
            capture.exports += (
                _metric(
                    now - 1,
                    now,
                    name="http.server.request.duration",
                ),
            )
        elif action_complete.exists() and len(capture.exports) == 1:
            now = tick()
            capture.exports += (
                _metric(
                    now - 1,
                    now,
                    name="http.server.request.duration",
                ),
            )

    capture = _Capture(on_snapshot=emit_boundaries)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.5,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED
    assert result.telemetry.metric_names == (
        "http.server.request.duration",
    )


def test_boundaries_landing_after_a_snapshot_are_not_slept_through(
    tmp_path: Path,
) -> None:
    """The capture can change between reading a snapshot and waiting on it.

    Both the readiness wait and the action wait read a snapshot and then park
    on the condition. A change announced in between is announced to nobody, so
    waiting on it can only end in the window timeout — nothing else is coming.
    """

    action_complete = tmp_path / "action-complete"
    command = _driver(
        tmp_path,
        f"""
import json, pathlib, sys, time
print(json.dumps({{"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
json.loads(sys.stdin.readline())
pathlib.Path({str(action_complete)!r}).write_text("done")
print(json.dumps({{"version": "jsonl-v1", "type": "action_complete", "sequence": 1, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
sys.stdin.read()
print(json.dumps({{"version": "jsonl-v1", "type": "stopped", "sequence": 2}}), flush=True)
""",
    )
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )
    tick = _clock()

    def land_after_the_snapshot(capture: _Capture) -> None:
        if not capture.exports:
            now = tick()
            capture.exports += (
                _metric(
                    now - 1, now, name="http.server.request.duration"
                ),
            )
            capture.announce()
        elif action_complete.exists() and len(capture.exports) == 1:
            now = tick()
            capture.exports += (
                _metric(
                    now - 1, now, name="http.server.request.duration"
                ),
            )
            capture.announce()

    capture = _Capture(after_snapshot=land_after_the_snapshot)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.5,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED
    assert result.telemetry.metric_names == (
        "http.server.request.duration",
    )


def test_a_span_landing_after_a_snapshot_seals_its_action(
    tmp_path: Path,
) -> None:
    """The same race, on the span the action is judged on."""

    action_complete = tmp_path / "action-trace-id"
    command = _driver(
        tmp_path,
        f"""
import json, pathlib, sys, time
print(json.dumps({{"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
action = json.loads(sys.stdin.readline())
pathlib.Path({str(action_complete)!r}).write_text(action["correlation_trace_id"])
print(json.dumps({{"version": "jsonl-v1", "type": "action_complete", "sequence": 1, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}}), flush=True)
sys.stdin.read()
print(json.dumps({{"version": "jsonl-v1", "type": "stopped", "sequence": 2}}), flush=True)
""",
    )
    scenario = replace(
        _scenario(command),
        spans=(SpanExpectation(match=SpanMatch(attributes={}), count=1),),
    )
    tick = _clock()

    def land_after_the_snapshot(capture: _Capture) -> None:
        if capture.exports or not action_complete.exists():
            return
        trace_id = action_complete.read_text()
        capture.exports += (_trace(trace_id, tick(), tick()),)
        capture.announce()

    capture = _Capture(after_snapshot=land_after_the_snapshot)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.5,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED
    assert [span.name for span in result.telemetry.spans] == [
        result.trace_id[-4:]
    ]


def test_readiness_metric_before_ready_never_isolates_bootstrap(
    tmp_path: Path,
) -> None:
    command = _driver(tmp_path, _SUCCESS_DRIVER)
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )
    stale = time.time_ns()
    capture = _Capture(
        exports=(
            _metric(
                stale - 10, stale, name="http.server.request.duration"
            ),
        )
    )

    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.2,
        settle_delay=0.001,
    ).run()

    assert "timed out isolating readiness telemetry" in (result.failure or "")


def test_readiness_telemetry_exported_late_stays_out_of_the_first_action(
    tmp_path: Path,
) -> None:
    """A cold runtime exports readiness after the first action is under way."""

    command = _driver(tmp_path, _SUCCESS_DRIVER)
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )
    readiness_trace = "0" * 31 + "1"
    readiness_end = 0
    tick = _clock()

    def emit(capture: _Capture) -> None:
        nonlocal readiness_end
        if not capture.exports:
            readiness_end = tick()
            capture.exports += (
                _metric(
                    readiness_end - 10,
                    readiness_end,
                    name="http.server.request.duration",
                ),
            )
        elif len(capture.exports) == 1:
            # The readiness span itself only lands once the action is open.
            now = tick()
            capture.exports += (
                _trace(
                    readiness_trace, readiness_end - 8, readiness_end - 2
                ),
                _metric(
                    now - 1, now, name="http.server.request.duration"
                ),
            )

    capture = _Capture(on_snapshot=emit)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.5,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED
    assert result.telemetry.spans == ()


def test_windows_settle_when_an_interval_closes_before_the_answer(
    tmp_path: Path,
) -> None:
    """The answer can reach the driver after the export it caused.

    An instrumentation records what it measured before it answers, so the
    interval holding that measurement can close while the response is still
    travelling. Judging the window by when the answer arrived, or by when
    its record was read, leaves nothing left to wait for.
    """

    ready_stamp = tmp_path / "ready-stamp"
    action_stamp = tmp_path / "action-stamp"
    command = _driver(
        tmp_path,
        f"""
import json, pathlib, sys, time
started = time.time_ns()
pathlib.Path({str(ready_stamp)!r}).write_text(str(started))
time.sleep(0.2)
print(json.dumps({{"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": started, "completed_unix_nano": time.time_ns()}}), flush=True)
last = 0
for line in sys.stdin:
    last = json.loads(line)["sequence"]
    started = time.time_ns()
    pathlib.Path({str(action_stamp)!r}).write_text(str(started))
    time.sleep(0.2)
    print(json.dumps({{"version": "jsonl-v1", "type": "action_complete", "sequence": last, "started_unix_nano": started, "completed_unix_nano": time.time_ns()}}), flush=True)
print(json.dumps({{"version": "jsonl-v1", "type": "stopped", "sequence": last + 1}}), flush=True)
""",
    )
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )

    def close_an_interval_mid_exchange(capture: _Capture) -> None:
        stamp = ready_stamp if not capture.exports else action_stamp
        if len(capture.exports) > 1 or not stamp.is_file():
            return
        closed = int(stamp.read_text()) + 1000
        capture.exports += (
            _metric(
                closed - 10, closed, name="http.server.request.duration"
            ),
        )

    capture = _Capture(on_snapshot=close_an_interval_mid_exchange)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=2.0,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED


def test_a_slow_start_is_bounded_by_the_scenario_timeout(
    tmp_path: Path,
) -> None:
    """Starting a runtime is not settling a window.

    A cold runtime can take far longer to listen than any telemetry takes
    to arrive once it has, so the window timeout must not decide whether it
    ever got there.
    """

    command = _driver(
        tmp_path,
        """
import json, sys, time
time.sleep(0.4)
print(json.dumps({"version": "jsonl-v1", "type": "ready", "sequence": 0, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
last = 0
for line in sys.stdin:
    last = json.loads(line)["sequence"]
    print(json.dumps({"version": "jsonl-v1", "type": "action_complete", "sequence": last, "started_unix_nano": time.time_ns(), "completed_unix_nano": time.time_ns()}), flush=True)
print(json.dumps({"version": "jsonl-v1", "type": "stopped", "sequence": last + 1}), flush=True)
""",
    )

    (result,) = PersistentController(
        (_scenario(command),),
        capture=cast(OtlpCaptureProxy, _Capture()),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.1,
        settle_delay=0.001,
        startup_timeout=5.0,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED


def test_missing_post_response_boundary_waits_until_timeout(
    tmp_path: Path,
) -> None:
    command = _driver(tmp_path, _SUCCESS_DRIVER)
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )

    def emit_readiness_only(capture: _Capture) -> None:
        if capture.exports:
            return
        now = time.time_ns()
        capture.exports += (
            _metric(now - 1, now, name="http.server.request.duration"),
        )
    capture = _Capture(on_snapshot=emit_readiness_only)
    started = time.monotonic()

    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=0.2,
        settle_delay=0.001,
    ).run()

    elapsed = time.monotonic() - started
    assert "timed out sealing action sequence 1" in (result.failure or "")
    assert 0.18 <= elapsed < 0.7


def test_self_reporting_sdk_metrics_do_not_block_sealing(
    tmp_path: Path,
) -> None:
    """An SDK that exports its own queue depth forever still seals actions."""

    command = _driver(tmp_path, _SUCCESS_DRIVER)
    scenario = replace(
        _scenario(command), metrics=("http.server.request.duration",)
    )
    duration_exports = 0
    tick = _clock()

    def emit(capture: _Capture) -> None:
        nonlocal duration_exports
        now = tick()
        if duration_exports < 2:
            duration_exports += 1
            capture.exports += (
                _metric(
                    now - 1, now, name="http.server.request.duration"
                ),
            )
            return
        capture.exports += (
            _metric(
                now - 1,
                now,
                name="queueSize",
                monotonic=False,
                scope="io.opentelemetry.sdk.trace",
            ),
        )

    capture = _Capture(on_snapshot=emit)
    (result,) = PersistentController(
        (scenario,),
        capture=cast(OtlpCaptureProxy, capture),
        cwd=tmp_path,
        env=os.environ,
        timeout=1.0,
        settle_delay=0.001,
    ).run()

    assert result.failure is None
    assert result.state is ActionState.SEALED
    assert result.telemetry.metric_names == (
        "http.server.request.duration",
    )


def test_multiple_delta_exports_stay_in_one_action_window() -> None:
    action = (_window("first", 1, "01" * 16, 100),)

    partition = partition_persistent_exports(
        (_metric(90, 105), _metric(105, 115)), action, 200
    )

    assert partition.windows[0].metric_names == ("requests", "requests")
    assert partition.metric_boundaries == ((105, 115),)


def test_cumulative_and_overlapping_metrics_are_rejected() -> None:
    actions = (
        _window("first", 1, "01" * 16, 100),
        _window("second", 2, "02" * 16, 200),
    )
    with pytest.raises(PersistentProtocolError, match="cumulative"):
        partition_persistent_exports(
            (
                _metric(
                    100,
                    150,
                    metrics_pb2.AGGREGATION_TEMPORALITY_CUMULATIVE,
                ),
            ),
            actions,
            300,
        )
    with pytest.raises(PersistentProtocolError, match="overlaps"):
        partition_persistent_exports((_metric(105, 205),), actions, 300)


def test_cumulative_up_down_counter_is_a_snapshot() -> None:
    """Its point is the current value, so its timestamp places it."""

    actions = (
        _window("first", 1, "01" * 16, 100),
        _window("second", 2, "02" * 16, 200),
    )

    partition = partition_persistent_exports(
        (
            _metric(
                1,
                205,
                metrics_pb2.AGGREGATION_TEMPORALITY_CUMULATIVE,
                name="http.server.active_requests",
                monotonic=False,
            ),
        ),
        actions,
        300,
    )

    assert partition.windows[0].metric_names == ()
    assert partition.windows[1].metric_names == (
        "http.server.active_requests",
    )
    # A snapshot proves nothing about a delta interval having closed.
    assert partition.metric_boundaries == ((), ())


def test_readiness_telemetry_lands_in_the_bootstrap_window() -> None:
    actions = (_window("first", 1, "01" * 16, 100),)

    partition = partition_persistent_exports(
        (_trace("0" * 31 + "1", 40, 60), _trace("01" * 16, 110, 120)),
        actions,
        200,
        50,
    )

    assert [span.name for span in partition.bootstrap.spans] == ["0001"]
    assert [span.name for span in partition.windows[0].spans] == ["0101"]


def test_metric_spanning_readiness_and_the_first_action_is_rejected() -> None:
    actions = (_window("first", 1, "01" * 16, 100),)

    with pytest.raises(PersistentProtocolError, match="overlaps"):
        partition_persistent_exports((_metric(40, 110),), actions, 200, 50)


def test_metric_missing_timestamps_is_rejected() -> None:
    with pytest.raises(
        PersistentProtocolError, match="missing point timestamps"
    ):
        partition_persistent_exports(
            (_metric(0, 150),),
            (_window("first", 1, "01" * 16, 100),),
            200,
        )


class _WatchedCondition:
    """A condition that reports when something has parked on it.

    Handing the parking over rather than sleeping on it is what makes the
    ordering below a fact rather than a likelihood. Every wait is recorded
    with the timeout it was given, which is how a loop that parks is told
    apart from one that re-reads the same state at full speed.
    """

    def __init__(self, condition: Condition) -> None:
        self._condition = condition
        self.waiting = Event()
        self.waits: list[float | None] = []

    def __enter__(self) -> None:
        self._condition.acquire()

    def __exit__(self, *_args: object) -> None:
        self._condition.release()

    def wait(self, timeout: float | None = None) -> bool:
        self.waiting.set()
        self.waits.append(timeout)
        return self._condition.wait(timeout)

    def notify_all(self) -> None:
        self._condition.notify_all()


def _watched(
    tmp_path: Path,
    capture: _Capture | None = None,
    *,
    timeout: float = 5.0,
    settle_delay: float = DEFAULT_SETTLE_DELAY,
) -> tuple[PersistentController, _WatchedCondition]:
    controller = PersistentController(
        (_scenario(("driver",)),),
        capture=cast(OtlpCaptureProxy, capture or _Capture()),
        cwd=tmp_path,
        env=os.environ,
        timeout=timeout,
        settle_delay=settle_delay,
    )
    watched = _WatchedCondition(controller._condition)
    controller._condition = cast(Condition, watched)
    return controller, watched


def test_an_exit_read_before_the_final_record_is_not_an_early_exit(
    tmp_path: Path,
) -> None:
    """One thread reaps the process, another reads what it last wrote.

    The driver writes ``stopped`` and exits, so the exit code can be published
    while that record is still on its way through the reader. Treating the
    exit as early there would fail a batch that finished.
    """

    controller, watched = _watched(tmp_path)
    controller._returncode = 0

    outcome: list[object] = []

    def expect() -> None:
        try:
            outcome.append(
                controller._expect_message(
                    "stopped", 2, time.monotonic() + 30
                )
            )
        except BaseException as error:  # noqa: BLE001
            outcome.append(error)

    reader = Thread(target=expect, daemon=True)
    reader.start()
    if not watched.waiting.wait(30):
        reader.join(timeout=5)
        pytest.fail(f"the final record was never waited for: {outcome}")

    line = json.dumps(
        {"version": "jsonl-v1", "type": "stopped", "sequence": 2}
    )
    with controller._condition:
        controller._messages.append(
            _Message(document=json.loads(line), line=line)
        )
        controller._stdout_closed = True
        controller._condition.notify_all()
    reader.join(timeout=30)

    assert not reader.is_alive()
    assert [getattr(item, "line", item) for item in outcome] == [line]


def test_an_exit_with_nothing_left_to_read_is_an_early_exit(
    tmp_path: Path,
) -> None:
    controller, _ = _watched(tmp_path)
    with controller._condition:
        controller._returncode = 3
        controller._raise_async_failure()
        controller._stdout_closed = True
        with pytest.raises(
            PersistentProtocolError, match="exited early with 3"
        ):
            controller._raise_async_failure()

    with pytest.raises(PersistentProtocolError, match="exited early with 3"):
        controller._expect_message("stopped", 2, time.monotonic() + 30)
class _FakeStdin:
    """The driver's end of the pipe, for a loop test that starts no process."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, text: str) -> int:
        self.written.append(text)
        return len(text)

    def flush(self) -> None:
        return None


def _answered(
    controller: PersistentController, sequence: int
) -> _ActionWindow:
    """An action whose response is already waiting to be read.

    The settling loop is what these tests are about, so the exchange that
    precedes it is handed over rather than driven through a process.
    """

    now = time.time_ns()
    document = {
        "version": "jsonl-v1",
        "type": "action_complete",
        "sequence": sequence,
        "started_unix_nano": now,
        "completed_unix_nano": now,
    }
    controller._process = cast(
        "subprocess.Popen[str]", SimpleNamespace(stdin=_FakeStdin())
    )
    controller._messages.append(
        _Message(document=document, line=json.dumps(document))
    )
    return _ActionWindow(
        scenario=controller._scenarios[sequence - 1],
        sequence=sequence,
        trace_id="11" * 16,
    )


def test_an_action_settling_on_an_in_flight_export_waits_for_it(
    tmp_path: Path,
) -> None:
    """The window is judged quiet, but the capture is still carrying an export.

    Sealing there would judge the action on telemetry the capture has not
    finished recording, so the loop keeps waiting. What it must not do is
    re-read the same snapshot at full speed until the export lands: the
    capture wakes it when that happens.
    """

    capture = _Capture(in_flight=1)
    controller, watched = _watched(
        tmp_path, capture, timeout=5.0, settle_delay=0.0
    )

    def land_once_it_parks(capture: _Capture) -> None:
        # The escape hatch is what a spinning loop hits, so this test fails on
        # its assertions rather than on the action deadline.
        if len(watched.waits) >= 2 or capture.snapshot_calls >= 40:
            capture.in_flight = 0

    capture.on_snapshot = land_once_it_parks
    action = _answered(controller, 1)

    controller._run_action(
        action, [action], capture.open_window("batch"), time.time_ns()
    )

    assert action.state is ActionState.SEALED
    assert watched.waits, "the loop never parked on the condition"
    assert all(waited == _IN_FLIGHT_WAIT_SECONDS for waited in watched.waits)
    assert capture.snapshot_calls == len(watched.waits) + 1


def test_an_action_that_never_goes_quiet_times_out_without_spinning(
    tmp_path: Path,
) -> None:
    """An export that never lands ends the action on its own deadline."""

    capture = _Capture(in_flight=1)
    controller, watched = _watched(
        tmp_path, capture, timeout=0.3, settle_delay=0.0
    )
    action = _answered(controller, 1)

    with pytest.raises(TimeoutError, match="sealing action sequence 1"):
        controller._run_action(
            action, [action], capture.open_window("batch"), time.time_ns()
        )

    assert action.state is ActionState.SETTLING
    # 0.3s of deadline in slices of _IN_FLIGHT_WAIT_SECONDS, not a spin.
    assert 1 <= len(watched.waits) <= 10
    assert all(
        waited is not None and 0 < waited <= _IN_FLIGHT_WAIT_SECONDS
        for waited in watched.waits
    )


def test_bootstrap_settling_on_an_in_flight_export_waits_for_it(
    tmp_path: Path,
) -> None:
    """The same quiet instant, on the window that isolates readiness."""

    capture = _Capture()
    controller, watched = _watched(
        tmp_path, capture, timeout=5.0, settle_delay=0.0
    )
    ready_unix_nano = time.time_ns()

    def hold_then_land(capture: _Capture) -> None:
        if capture.snapshot_calls == 1:
            return
        if len(watched.waits) >= 2 or capture.snapshot_calls >= 40:
            capture.in_flight = 0
        else:
            capture.in_flight = 1

    capture.on_snapshot = hold_then_land

    boundary = controller._wait_for_bootstrap(
        capture.open_window("batch"), ready_unix_nano
    )

    assert boundary == ready_unix_nano
    assert watched.waits, "the loop never parked on the condition"
    assert all(waited == _IN_FLIGHT_WAIT_SECONDS for waited in watched.waits)


def test_bootstrap_that_never_goes_quiet_times_out_without_spinning(
    tmp_path: Path,
) -> None:
    capture = _Capture()
    controller, watched = _watched(
        tmp_path, capture, timeout=0.3, settle_delay=0.0
    )

    def hold(capture: _Capture) -> None:
        if capture.snapshot_calls > 1:
            capture.in_flight = 1

    capture.on_snapshot = hold

    with pytest.raises(TimeoutError, match="isolating readiness telemetry"):
        controller._wait_for_bootstrap(
            capture.open_window("batch"), time.time_ns()
        )

    assert 1 <= len(watched.waits) <= 10
    assert all(
        waited is not None and 0 < waited <= _IN_FLIGHT_WAIT_SECONDS
        for waited in watched.waits
    )
