# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The jsonl-v1 persistent scenario process and action windows."""

from __future__ import annotations

import json
import secrets
import subprocess
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from threading import Condition, Thread
from typing import IO, Any, cast

from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2

from ._checks import selects
from ._otlp_capture import (
    CapturedExport,
    CapturedWindow,
    CaptureWindow,
    ExportRequest,
    OtlpCaptureProxy,
    decode_window,
    self_monitoring,
)
from ._spec import ScenarioSpec

PROTOCOL_VERSION = "jsonl-v1"
DEFAULT_WINDOW_TIMEOUT = 10.0
DEFAULT_SETTLE_DELAY = 0.25
# The longest a settling loop parks on the condition once its settle delay is
# up and the capture is still carrying an export. Every arrival and completion
# wakes the condition, so this only bounds a wait nothing else ends; what it
# rules out is re-reading the same snapshot at full speed until the export
# lands.
_IN_FLIGHT_WAIT_SECONDS = 0.05

PERSISTENT_ENV = {
    "OTEL_BSP_SCHEDULE_DELAY": "50",
    "OTEL_BLRP_SCHEDULE_DELAY": "50",
    "OTEL_METRIC_EXPORT_INTERVAL": "100",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "delta",
}


class ActionState(Enum):
    """The lifecycle of one persistent action's telemetry window."""

    OPEN = auto()
    RESPONSE_COMPLETE = auto()
    PROVISIONALLY_SATISFIED = auto()
    SETTLING = auto()
    SEALED = auto()


class PersistentProtocolError(RuntimeError):
    """The driver or its telemetry made safe windowing impossible."""


@dataclass(frozen=True)
class PersistentActionResult:
    """One action after the persistent process and final telemetry drain."""

    scenario: ScenarioSpec
    trace_id: str
    state: ActionState
    transitions: tuple[ActionState, ...]
    telemetry: CapturedWindow
    failure: str | None
    stdout: str
    stderr: str
    executed: bool


@dataclass
class _ActionWindow:
    scenario: ScenarioSpec
    sequence: int
    trace_id: str
    state: ActionState = ActionState.OPEN
    transitions: list[ActionState] = field(
        default_factory=lambda: [ActionState.OPEN]
    )
    sent_unix_nano: int = 0
    requested_unix_nano: int | None = None
    response_unix_nano: int | None = None
    sealed_unix_nano: int | None = None
    stdout: list[str] = field(default_factory=list[str])

    def transition(self, state: ActionState) -> None:
        allowed = {
            ActionState.OPEN: ActionState.RESPONSE_COMPLETE,
            ActionState.RESPONSE_COMPLETE: (
                ActionState.PROVISIONALLY_SATISFIED
            ),
            ActionState.PROVISIONALLY_SATISFIED: ActionState.SETTLING,
            ActionState.SETTLING: ActionState.SEALED,
        }
        if allowed.get(self.state) is not state:
            raise AssertionError(
                f"invalid action transition {self.state} -> {state}"
            )
        self.state = state
        self.transitions.append(state)


@dataclass(frozen=True)
class _Message:
    document: Mapping[str, object]
    line: str


@dataclass(frozen=True)
class _Partition:
    bootstrap: CapturedWindow
    windows: tuple[CapturedWindow, ...]
    metric_boundaries: tuple[tuple[int, ...], ...]


class PersistentController:
    """Run ordered scenarios through one jsonl-v1 driver process."""

    def __init__(
        self,
        scenarios: Sequence[ScenarioSpec],
        *,
        capture: OtlpCaptureProxy,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float = DEFAULT_WINDOW_TIMEOUT,
        settle_delay: float = DEFAULT_SETTLE_DELAY,
        startup_timeout: float | None = None,
    ) -> None:
        if not scenarios:
            raise ValueError("A persistent batch needs at least one scenario")
        run_spec = scenarios[0].run_spec
        if run_spec.protocol != PROTOCOL_VERSION:
            raise ValueError(
                "PersistentController requires jsonl-v1 scenarios"
            )
        if any(item.run_spec != run_spec for item in scenarios[1:]):
            raise ValueError(
                "Persistent scenarios in one batch must share a run command"
            )
        self._scenarios = tuple(scenarios)
        self._command = run_spec.command
        self._capture = capture
        self._cwd = cwd
        self._env = dict(env)
        self._timeout = timeout
        self._settle_delay = settle_delay
        # Starting a runtime is not settling a window: a cold JVM, .NET or
        # Node process can take far longer to listen than any telemetry
        # takes to arrive once it does. The driver has its own startup
        # timeout and says what went wrong, so leave room to hear it.
        self._startup_timeout = (
            timeout
            if startup_timeout is None
            else max(startup_timeout, timeout)
        )
        self._condition = Condition()
        self._messages: deque[_Message] = deque()
        self._reader_error: str | None = None
        self._stdout_closed = False
        self._stderr_closed = False
        self._returncode: int | None = None
        # Counts what the capture has told this controller about, so a change
        # that lands between reading a snapshot and waiting on it is seen
        # rather than slept through.
        self._capture_changes = 0
        self._stderr: list[str] = []
        self._all_stdout: list[str] = []
        self._process: subprocess.Popen[str] | None = None
        self._stdin_closed = False
        self.readiness: CapturedWindow = _empty_window("readiness", 0)

    def run(self) -> tuple[PersistentActionResult, ...]:
        """Execute the batch, aborting every remaining action after a failure."""

        batch_window = self._capture.open_window(
            f"persistent:{self._scenarios[0].name}"
        )
        self._capture.set_change_notifier(self._notify)
        actions: list[_ActionWindow] = []
        ready_unix_nano = 0
        bootstrap_unix_nano = 0
        failure: str | None = None
        failed_index = 0
        batch_end = time.time_ns()
        final: CapturedWindow | None = None
        reconciliation_failure = False
        try:
            try:
                self._start_process()
                ready = self._expect_message(
                    "ready", 0, time.monotonic() + self._startup_timeout
                )
                ready_unix_nano, _ = _exchange_stamps(ready)
                bootstrap_unix_nano = self._wait_for_bootstrap(
                    batch_window, ready_unix_nano
                )
                for index, scenario in enumerate(self._scenarios):
                    failed_index = index
                    action = _ActionWindow(
                        scenario=scenario,
                        sequence=index + 1,
                        trace_id=_trace_id(),
                    )
                    actions.append(action)
                    self._run_action(
                        action, actions, batch_window, bootstrap_unix_nano
                    )
                failed_index = len(self._scenarios)
                self._close_stdin()
                deadline = time.monotonic() + self._timeout
                self._expect_message(
                    "stopped", len(self._scenarios) + 1, deadline
                )
                self._wait_for_exit(deadline)
                if self._returncode != 0:
                    raise PersistentProtocolError(
                        f"persistent driver exited with {self._returncode}"
                    )
            except (OSError, PersistentProtocolError, TimeoutError) as error:
                failure = str(error)
                self._abort_process()

            batch_end = time.time_ns()
            try:
                self._capture.drain(timeout=self._timeout)
            except TimeoutError as error:
                failure = failure or str(error)
            try:
                final = self._capture.close_window(
                    batch_window, timeout=self._timeout
                )
            except TimeoutError as error:
                failure = failure or str(error)
                final = decode_window(
                    batch_window, self._capture.requests(batch_window)
                )
        finally:
            self._capture.set_change_notifier(None)
            self._abort_process()

        assert final is not None
        try:
            partition = partition_persistent_exports(
                final.exports, actions, batch_end, bootstrap_unix_nano
            )
        except PersistentProtocolError as error:
            failure = failure or str(error)
            reconciliation_failure = True
            partition = _empty_partition(actions)
        self.readiness = partition.bootstrap

        return self._results(
            actions,
            partition,
            failure=failure,
            failed_index=failed_index,
            fail_all=reconciliation_failure,
        )

    def _start_process(self) -> None:
        try:
            process = subprocess.Popen(  # noqa: S603
                self._command,
                cwd=self._cwd,
                env=self._env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            raise PersistentProtocolError(
                f"could not start persistent driver: {error}"
            ) from error
        self._process = process
        assert process.stdout is not None
        assert process.stderr is not None
        Thread(
            target=self._read_stdout,
            args=(process.stdout,),
            name="conformance-jsonl-stdout",
            daemon=True,
        ).start()
        Thread(
            target=self._read_stderr,
            args=(process.stderr,),
            name="conformance-jsonl-stderr",
            daemon=True,
        ).start()
        Thread(
            target=self._wait_process,
            args=(process,),
            name="conformance-jsonl-process",
            daemon=True,
        ).start()

    def _read_stdout(self, stream: IO[str]) -> None:
        try:
            for raw in stream:
                line = raw.removesuffix("\n").removesuffix("\r")
                with self._condition:
                    self._all_stdout.append(line)
                try:
                    loaded: object = json.loads(
                        line,
                        parse_constant=lambda value: _raise_json(value),
                    )
                    if not isinstance(loaded, dict):
                        raise ValueError("record is not a JSON object")
                    document = cast(dict[str, object], loaded)
                    message = _Message(document=document, line=line)
                except (json.JSONDecodeError, ValueError) as error:
                    with self._condition:
                        self._reader_error = (
                            f"malformed jsonl-v1 record {line!r}: {error}"
                        )
                        self._condition.notify_all()
                    return
                with self._condition:
                    self._messages.append(message)
                    self._condition.notify_all()
        finally:
            with self._condition:
                self._stdout_closed = True
                self._condition.notify_all()

    def _read_stderr(self, stream: IO[str]) -> None:
        for line in stream:
            with self._condition:
                self._stderr.append(line)
                self._condition.notify_all()
        with self._condition:
            self._stderr_closed = True
            self._condition.notify_all()

    def _wait_process(self, process: subprocess.Popen[str]) -> None:
        returncode = process.wait()
        with self._condition:
            self._returncode = returncode
            self._condition.notify_all()

    def _expect_message(
        self, expected_type: str, sequence: int, deadline: float
    ) -> _Message:
        while True:
            with self._condition:
                if self._reader_error is not None:
                    raise PersistentProtocolError(self._reader_error)
                if self._messages:
                    message = self._messages.popleft()
                    break
                if self._exited_early():
                    raise PersistentProtocolError(
                        f"persistent driver exited early with "
                        f"{self._returncode}"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"timed out waiting for {expected_type} sequence "
                        f"{sequence}"
                    )
                self._condition.wait(remaining)
        _validate_message(message.document, expected_type, sequence)
        return message

    def _wait_for_bootstrap(
        self, batch_window: CaptureWindow, ready_unix_nano: int
    ) -> int:
        """Hold the first action until readiness telemetry is behind us.

        Readiness is a real request, so its measurements sit in whatever
        aggregation interval was open when it ran. Nothing else has been
        measured yet, so a declared metric closing at or after the readiness
        request went out is that interval, and no later point can mix
        readiness with an action. Waiting for a positive signal rather than
        for quiet keeps this immune to a cold runtime whose first export is
        slow.

        ``ready_unix_nano`` is when the driver sent readiness. The instant
        the answer came back is later than the measurement by however long
        the response took to travel, which is enough for an interval to
        close in between and leave nothing left to wait for.

        Returns the boundary that divides readiness from the first action,
        read from the instrumentation's own clock where it reported one.
        """
        required_metrics = {
            metric
            for scenario in self._scenarios
            for metric in scenario.metrics or ()
        }
        started = time.monotonic()
        deadline = started + self._timeout
        settle_deadline: float | None = None
        fingerprint: object = None
        while True:
            changes = self._observed_capture_changes()
            snapshot = self._capture.snapshot(batch_window)
            captured = decode_window(batch_window, snapshot.exports)
            if snapshot.in_flight == 0:
                if required_metrics:
                    closed = [
                        end
                        for end in _metric_point_ends(
                            captured, frozenset(required_metrics)
                        )
                        if end >= ready_unix_nano
                    ]
                    if closed:
                        return max(closed)
                else:
                    # No metric window to close, so nothing can aggregate
                    # readiness together with an action. Settling on the
                    # bootstrap window's own content is enough.
                    current = _window_fingerprint(captured, None)
                    if current != fingerprint:
                        fingerprint = current
                        settle_deadline = (
                            time.monotonic() + self._settle_delay
                        )
                    elif (
                        settle_deadline is not None
                        and time.monotonic() >= settle_deadline
                    ):
                        return ready_unix_nano

            with self._condition:
                self._raise_async_failure()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    expected = sorted(required_metrics)
                    detail = (
                        f"; expected one of {expected} to close at or after "
                        "the readiness request"
                        if expected
                        else ""
                    )
                    raise TimeoutError(
                        f"timed out isolating readiness telemetry{detail}"
                    )
                wait_until = deadline
                if settle_deadline is not None:
                    wait_until = min(wait_until, settle_deadline)
                if self._capture_changes != changes:
                    continue
                wait_for = wait_until - time.monotonic()
                if wait_for <= 0:
                    if snapshot.in_flight == 0:
                        continue
                    # The bootstrap window has settled but the capture is
                    # still carrying an export that belongs in it. Park for a
                    # slice of what is left of the bootstrap deadline: the
                    # capture wakes this the moment the export lands.
                    wait_for = min(remaining, _IN_FLIGHT_WAIT_SECONDS)
                self._condition.wait(wait_for)

    def _run_action(
        self,
        action: _ActionWindow,
        actions: Sequence[_ActionWindow],
        batch_window: CaptureWindow,
        bootstrap_unix_nano: int,
    ) -> None:
        process = self._process
        assert process is not None
        assert process.stdin is not None
        record = {
            "version": PROTOCOL_VERSION,
            "type": "action",
            "sequence": action.sequence,
            "scenario": action.scenario.name,
            "correlation_trace_id": action.trace_id,
            "action": dict(action.scenario.action or {}),
        }
        action.sent_unix_nano = time.time_ns()
        try:
            process.stdin.write(
                json.dumps(
                    record,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise PersistentProtocolError(
                f"could not send action sequence {action.sequence}: {error}"
            ) from error

        deadline = time.monotonic() + self._timeout
        message = self._expect_action_response(action.sequence, deadline)
        action.stdout.append(message.line)
        action.requested_unix_nano, action.response_unix_nano = (
            _exchange_stamps(message)
        )
        action.transition(ActionState.RESPONSE_COMPLETE)

        settle_deadline: float | None = None
        fingerprint: object = None
        while action.state is not ActionState.SEALED:
            changes = self._observed_capture_changes()
            snapshot = self._capture.snapshot(batch_window)
            now_unix_nano = time.time_ns()
            try:
                partition = partition_persistent_exports(
                    snapshot.exports,
                    actions,
                    now_unix_nano,
                    bootstrap_unix_nano,
                )
            except PersistentProtocolError as error:
                raise PersistentProtocolError(
                    f"{action.scenario.display_name}: {error}"
                ) from error
            current = partition.windows[-1]
            boundary = partition.metric_boundaries[-1]
            satisfied = _positive_expectations_satisfied(
                action, current, boundary
            )
            # What the action is judged on, rather than every arrival: an SDK
            # that reports on itself exports on every interval forever, and
            # waiting for that to stop would never seal an action.
            observed = _window_fingerprint(current, action.scenario.metrics)

            if action.state is ActionState.RESPONSE_COMPLETE and satisfied:
                action.transition(ActionState.PROVISIONALLY_SATISFIED)
                action.transition(ActionState.SETTLING)
                settle_deadline = time.monotonic() + self._settle_delay
                fingerprint = observed
            elif action.state is ActionState.SETTLING:
                if not satisfied:
                    action.state = ActionState.RESPONSE_COMPLETE
                    action.transitions.append(ActionState.RESPONSE_COMPLETE)
                    settle_deadline = None
                elif observed != fingerprint:
                    settle_deadline = time.monotonic() + self._settle_delay
                    fingerprint = observed
                elif (
                    settle_deadline is not None
                    and time.monotonic() >= settle_deadline
                    # Seal on a quiet instant, so nothing the window is
                    # judged on is still being recorded.
                    and snapshot.in_flight == 0
                ):
                    action.transition(ActionState.SEALED)
                    action.sealed_unix_nano = time.time_ns()
                    return

            with self._condition:
                self._raise_async_failure()
                if self._messages:
                    message = self._messages[0]
                    raise PersistentProtocolError(
                        "unexpected driver record while settling action "
                        f"{action.sequence}: {message.line}"
                    )
                wait_until = deadline
                if settle_deadline is not None:
                    wait_until = min(wait_until, settle_deadline)
                remaining = wait_until - time.monotonic()
                if remaining <= 0:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise TimeoutError(
                            f"timed out sealing action sequence "
                            f"{action.sequence}"
                        )
                    if snapshot.in_flight == 0:
                        continue
                    # The window has settled but the capture is still carrying
                    # an export that would land in it. Park for a slice of
                    # what is left of the action's deadline: the capture wakes
                    # this the moment the export lands.
                    remaining = min(left, _IN_FLIGHT_WAIT_SECONDS)
                if self._capture_changes != changes:
                    continue
                self._condition.wait(remaining)

    def _expect_action_response(
        self, sequence: int, deadline: float
    ) -> _Message:
        message = self._expect_message_any(deadline)
        document = message.document
        _validate_envelope(document, sequence)
        record_type = document["type"]
        if record_type == "action_error":
            detail = (
                document.get("error")
                or document.get("message")
                or message.line
            )
            raise PersistentProtocolError(
                f"action sequence {sequence} failed: {detail}"
            )
        if record_type != "action_complete":
            raise PersistentProtocolError(
                f"expected action_complete sequence {sequence}, got "
                f"{record_type!r}"
            )
        return message

    def _expect_message_any(self, deadline: float) -> _Message:
        while True:
            with self._condition:
                if self._messages:
                    return self._messages.popleft()
                self._raise_async_failure()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for action response")
                self._condition.wait(remaining)

    def _raise_async_failure(self) -> None:
        if self._reader_error is not None:
            raise PersistentProtocolError(self._reader_error)
        if self._exited_early():
            raise PersistentProtocolError(
                f"persistent driver exited early with {self._returncode}"
            )

    def _exited_early(self) -> bool:
        """Whether the driver is gone and everything it wrote has been read.

        A record the driver wrote just before exiting is still on its way
        through the reader thread when the process is reaped, so an exit alone
        says nothing about whether the batch finished. Standard output closing
        is what makes the record stream complete, which is the same pair
        :meth:`_wait_for_exit` waits for. Callers hold ``_condition``.
        """

        return self._returncode is not None and self._stdout_closed

    def _wait_for_exit(self, deadline: float) -> None:
        with self._condition:
            while (
                self._returncode is None
                or not self._stdout_closed
                or not self._stderr_closed
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "timed out waiting for persistent driver exit"
                    )
                self._condition.wait(remaining)
            if self._reader_error is not None:
                raise PersistentProtocolError(self._reader_error)
            if self._messages:
                raise PersistentProtocolError(
                    f"unexpected protocol record after stopped: "
                    f"{self._messages[0].line}"
                )

    def _close_stdin(self) -> None:
        if self._stdin_closed:
            return
        self._stdin_closed = True
        process = self._process
        if process is not None and process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass

    def _abort_process(self) -> None:
        self._close_stdin()
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        deadline = time.monotonic() + 1
        with self._condition:
            while not self._stdout_closed or not self._stderr_closed:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)

    def _notify(self) -> None:
        with self._condition:
            self._capture_changes += 1
            self._condition.notify_all()

    def _observed_capture_changes(self) -> int:
        """The change count to read a snapshot against.

        Read before the snapshot: the capture publishes a change and only then
        notifies, so anything this count misses is still ahead of the wait
        that follows.
        """

        with self._condition:
            return self._capture_changes

    def _results(
        self,
        actions: Sequence[_ActionWindow],
        partition: _Partition,
        *,
        failure: str | None,
        failed_index: int,
        fail_all: bool,
    ) -> tuple[PersistentActionResult, ...]:
        results: list[PersistentActionResult] = []
        stderr = "".join(self._stderr)
        diagnostic_failure = failure
        if failure is not None and stderr:
            diagnostic_failure = (
                f"{failure}\n--- driver stderr ---\n{stderr.rstrip()}"
            )
        failure_index = (
            min(failed_index, len(actions) - 1) if actions else failed_index
        )
        for index, scenario in enumerate(self._scenarios):
            if index < len(actions):
                action = actions[index]
                telemetry = partition.windows[index]
                executed = action.sent_unix_nano != 0
                action_failure = (
                    diagnostic_failure
                    if failure is not None
                    and (fail_all or index == failure_index)
                    else None
                )
                if failure is not None and index > failure_index:
                    action_failure = (
                        f"{scenario.display_name}: unexecuted; persistent "
                        f"batch aborted after action {failed_index + 1}: {failure}"
                    )
            else:
                action = _ActionWindow(
                    scenario=scenario,
                    sequence=index + 1,
                    trace_id="",
                )
                telemetry = _empty_window(scenario.name, index + 1)
                executed = False
                reason = diagnostic_failure or "driver failure"
                action_failure = (
                    f"{scenario.display_name}: unexecuted; persistent batch "
                    f"aborted: {reason}"
                )
            results.append(
                PersistentActionResult(
                    scenario=scenario,
                    trace_id=action.trace_id,
                    state=action.state,
                    transitions=tuple(action.transitions),
                    telemetry=telemetry,
                    failure=action_failure,
                    stdout="\n".join(action.stdout)
                    + ("\n" if action.stdout else ""),
                    stderr=stderr,
                    executed=executed,
                )
            )
        return tuple(results)


def partition_persistent_exports(
    exports: Sequence[CapturedExport],
    actions: Sequence[_ActionWindow],
    batch_end_unix_nano: int,
    bootstrap_unix_nano: int = 0,
) -> _Partition:
    """Assign raw OTLP records to action windows without aggregate subtraction.

    Assignment is driven by the timestamps the instrumentation itself
    reported, never by the order in which exports happened to arrive. The
    range before the first action is the bootstrap window: readiness
    telemetry belongs there however late its export lands.
    ``bootstrap_unix_nano`` is when the driver reported readiness, and is a
    boundary a metric point may not straddle, so no point may mix readiness
    with the first action.
    """

    if not actions:
        return _Partition(_empty_window("readiness", 0), (), ())
    # Where readiness ends and the first action begins. Taken from the
    # instrumentation's own clock when it reported one, because a coarse
    # system clock can put the driver's send at the same nanosecond as an
    # interval that closed before it.
    first_start = actions[0].sent_unix_nano
    if bootstrap_unix_nano:
        first_start = max(first_start, bootstrap_unix_nano + 1)
    starts: list[int] = []
    for index, action in enumerate(actions):
        start = first_start if index == 0 else action.sent_unix_nano
        if start <= 0:
            raise PersistentProtocolError("invalid action timing boundary")
        # A coarse clock can time two sends to the same nanosecond, which
        # leaves the earlier window empty rather than out of order.
        starts.append(max(start, starts[-1]) if starts else start)
    ranges = [
        (start, max(starts[index + 1], start))
        if index + 1 < len(starts)
        else (start, max(batch_end_unix_nano, start))
        for index, start in enumerate(starts)
    ]
    # Index 0 is the bootstrap window; action ``index`` is at ``index + 1``.
    ranges.insert(0, (0, starts[0]))
    response_boundaries = [
        bootstrap_unix_nano,
        *(
            action.response_unix_nano or batch_end_unix_nano
            for action in actions
        ),
    ]
    trace_ids = {
        bytes.fromhex(action.trace_id): index + 1
        for index, action in enumerate(actions)
        if action.trace_id
    }
    assigned: list[list[CapturedExport]] = [[] for _ in ranges]
    metric_boundaries: list[list[int]] = [[] for _ in ranges]
    declared = [
        frozenset(action.scenario.metrics)
        if action.scenario.metrics
        else None
        for action in actions
    ]
    declared.insert(0, None)

    for item in exports:
        requests: Mapping[int, ExportRequest]
        if isinstance(
            item.request, trace_service_pb2.ExportTraceServiceRequest
        ):
            requests = _partition_traces(item.request, trace_ids, ranges)
        elif isinstance(
            item.request, metrics_service_pb2.ExportMetricsServiceRequest
        ):
            requests, boundaries = _partition_metrics(
                item.request, ranges, response_boundaries, declared
            )
            for index, values in boundaries.items():
                metric_boundaries[index].extend(values)
        else:
            requests = _partition_logs(item.request, trace_ids, ranges)
        for index, request in requests.items():
            assigned[index].append(
                CapturedExport(
                    signal=item.signal,
                    request=request,
                    received_unix_nano=item.received_unix_nano,
                )
            )

    windows = tuple(
        decode_window(
            CaptureWindow(action.scenario.name, index + 1),
            tuple(assigned[index + 1]),
        )
        for index, action in enumerate(actions)
    )
    return _Partition(
        bootstrap=decode_window(
            CaptureWindow("readiness", 0), tuple(assigned[0])
        ),
        windows=windows,
        metric_boundaries=tuple(
            tuple(sorted(values)) for values in metric_boundaries[1:]
        ),
    )


def _partition_traces(
    request: trace_service_pb2.ExportTraceServiceRequest,
    trace_ids: Mapping[bytes, int],
    ranges: Sequence[tuple[int, int]],
) -> dict[int, trace_service_pb2.ExportTraceServiceRequest]:
    assignments: dict[tuple[int, int, int], int] = {}
    seen_trace_ids: dict[bytes, int] = {}
    for resource_index, resource in enumerate(request.resource_spans):
        for scope_index, scope in enumerate(resource.scope_spans):
            for span_index, span in enumerate(scope.spans):
                trace_id = bytes(span.trace_id)
                index = trace_ids.get(trace_id)
                if index is None:
                    index = _assign_interval(
                        span.start_time_unix_nano,
                        span.end_time_unix_nano,
                        ranges,
                        "span",
                    )
                previous = seen_trace_ids.setdefault(trace_id, index)
                if previous != index:
                    raise PersistentProtocolError(
                        "one trace overlaps multiple action windows"
                    )
                assignments[(resource_index, scope_index, span_index)] = index
    return _filtered_trace_requests(request, assignments)


def _filtered_trace_requests(
    request: trace_service_pb2.ExportTraceServiceRequest,
    assignments: Mapping[tuple[int, int, int], int],
) -> dict[int, trace_service_pb2.ExportTraceServiceRequest]:
    output: dict[int, trace_service_pb2.ExportTraceServiceRequest] = {}
    for index in sorted(set(assignments.values())):
        copied = trace_service_pb2.ExportTraceServiceRequest()
        copied.CopyFrom(request)
        for resource_index in reversed(range(len(copied.resource_spans))):
            resource = copied.resource_spans[resource_index]
            for scope_index in reversed(range(len(resource.scope_spans))):
                scope = resource.scope_spans[scope_index]
                for span_index in reversed(range(len(scope.spans))):
                    if (
                        assignments[(resource_index, scope_index, span_index)]
                        != index
                    ):
                        del scope.spans[span_index]
                if not scope.spans:
                    del resource.scope_spans[scope_index]
            if not resource.scope_spans:
                del copied.resource_spans[resource_index]
        output[index] = copied
    return output


def _partition_logs(
    request: logs_service_pb2.ExportLogsServiceRequest,
    trace_ids: Mapping[bytes, int],
    ranges: Sequence[tuple[int, int]],
) -> dict[int, logs_service_pb2.ExportLogsServiceRequest]:
    assignments: dict[tuple[int, int, int], int] = {}
    for resource_index, resource in enumerate(request.resource_logs):
        for scope_index, scope in enumerate(resource.scope_logs):
            for record_index, record in enumerate(scope.log_records):
                trace_id = bytes(record.trace_id)
                index = trace_ids.get(trace_id)
                if index is None:
                    timestamp = (
                        record.time_unix_nano or record.observed_time_unix_nano
                    )
                    index = _assign_interval(
                        timestamp, timestamp, ranges, "log record"
                    )
                assignments[(resource_index, scope_index, record_index)] = (
                    index
                )

    output: dict[int, logs_service_pb2.ExportLogsServiceRequest] = {}
    for index in sorted(set(assignments.values())):
        copied = logs_service_pb2.ExportLogsServiceRequest()
        copied.CopyFrom(request)
        for resource_index in reversed(range(len(copied.resource_logs))):
            resource = copied.resource_logs[resource_index]
            for scope_index in reversed(range(len(resource.scope_logs))):
                scope = resource.scope_logs[scope_index]
                for record_index in reversed(range(len(scope.log_records))):
                    if (
                        assignments[
                            (resource_index, scope_index, record_index)
                        ]
                        != index
                    ):
                        del scope.log_records[record_index]
                if not scope.log_records:
                    del resource.scope_logs[scope_index]
            if not resource.scope_logs:
                del copied.resource_logs[resource_index]
        output[index] = copied
    return output


def _partition_metrics(
    request: metrics_service_pb2.ExportMetricsServiceRequest,
    ranges: Sequence[tuple[int, int]],
    response_boundaries: Sequence[int],
    declared: Sequence[frozenset[str] | None],
) -> tuple[
    dict[int, metrics_service_pb2.ExportMetricsServiceRequest],
    dict[int, list[int]],
]:
    assignments: dict[tuple[int, int, int, int], int] = {}
    boundaries: dict[int, list[int]] = {}
    for resource_index, resource in enumerate(request.resource_metrics):
        for scope_index, scope in enumerate(resource.scope_metrics):
            for metric_index, metric in enumerate(scope.metrics):
                data_name = metric.WhichOneof("data")
                if data_name is None:
                    raise PersistentProtocolError(
                        f"metric {metric.name!r} has no data points"
                    )
                data = getattr(metric, data_name)
                points = data.data_points
                if not points:
                    raise PersistentProtocolError(
                        f"metric {metric.name!r} has no data points"
                    )
                snapshot = _reports_a_snapshot(
                    data_name, data
                ) or self_monitoring(scope.scope.name, metric.name)
                if data_name in (
                    "sum",
                    "histogram",
                    "exponential_histogram",
                ) and not snapshot:
                    if (
                        data.aggregation_temporality
                        != metrics_pb2.AGGREGATION_TEMPORALITY_DELTA
                    ):
                        raise PersistentProtocolError(
                            f"metric {metric.name!r} uses cumulative or "
                            "unspecified temporality; persistent windows "
                            "require delta"
                        )
                for point_index, point in enumerate(points):
                    end = point.time_unix_nano
                    start = getattr(point, "start_time_unix_nano", 0)
                    if snapshot:
                        start = end
                    elif data_name in (
                        "sum",
                        "histogram",
                        "exponential_histogram",
                    ):
                        if not start or not end:
                            raise PersistentProtocolError(
                                f"metric {metric.name!r} is missing point "
                                "timestamps needed for assignment"
                            )
                    else:
                        start = end
                    index = _assign_timestamp(
                        end, ranges, f"metric {metric.name!r}"
                    )
                    crossed = [
                        boundary
                        for boundary_index, boundary in enumerate(
                            response_boundaries
                        )
                        if boundary_index != index and start < boundary < end
                    ]
                    if crossed:
                        raise PersistentProtocolError(
                            f"metric {metric.name!r} overlaps action "
                            f"boundaries {crossed}: point=[{start}, {end}]"
                        )
                    assignments[
                        (
                            resource_index,
                            scope_index,
                            metric_index,
                            point_index,
                        )
                    ] = index
                    names = declared[index] if index < len(declared) else None
                    if not snapshot and (
                        names is None or metric.name in names
                    ):
                        boundaries.setdefault(index, []).append(end)

    output: dict[int, metrics_service_pb2.ExportMetricsServiceRequest] = {}
    for index in sorted(set(assignments.values())):
        copied = metrics_service_pb2.ExportMetricsServiceRequest()
        copied.CopyFrom(request)
        for resource_index in reversed(range(len(copied.resource_metrics))):
            resource = copied.resource_metrics[resource_index]
            for scope_index in reversed(range(len(resource.scope_metrics))):
                scope = resource.scope_metrics[scope_index]
                for metric_index in reversed(range(len(scope.metrics))):
                    metric = scope.metrics[metric_index]
                    data_name = metric.WhichOneof("data")
                    assert data_name is not None
                    points = getattr(metric, data_name).data_points
                    for point_index in reversed(range(len(points))):
                        if (
                            assignments[
                                (
                                    resource_index,
                                    scope_index,
                                    metric_index,
                                    point_index,
                                )
                            ]
                            != index
                        ):
                            del points[point_index]
                    if not points:
                        del scope.metrics[metric_index]
                if not scope.metrics:
                    del resource.scope_metrics[scope_index]
            if not resource.scope_metrics:
                del copied.resource_metrics[resource_index]
        output[index] = copied
    return output, boundaries


def _reports_a_snapshot(data_name: str, data: Any) -> bool:
    """Whether each point stands alone as a value read at one instant.

    Gauges do. So does a cumulative non-monotonic sum: an UpDownCounter is
    reported cumulatively even under the delta preference, and its point is
    the current value rather than an aggregate to be split across windows.
    A monotonic sum or a histogram is an aggregate over its interval, so a
    cumulative one covers the whole process and belongs to no window.
    """
    if data_name != "sum":
        return data_name == "gauge"
    return (
        not data.is_monotonic
        and data.aggregation_temporality
        == metrics_pb2.AGGREGATION_TEMPORALITY_CUMULATIVE
    )


def _assign_timestamp(
    timestamp: int,
    ranges: Sequence[tuple[int, int]],
    description: str,
) -> int:
    matches = [
        index
        for index, (window_start, window_end) in enumerate(ranges)
        if window_start <= timestamp
        and (
            timestamp < window_end
            or (
                index == len(ranges) - 1 and timestamp == window_end
            )
        )
    ]
    if len(matches) != 1:
        raise PersistentProtocolError(
            f"{description} is unassignable: timestamp={timestamp}, "
            f"actions={list(ranges)}"
        )
    return matches[0]


def _assign_interval(
    start: int,
    end: int,
    ranges: Sequence[tuple[int, int]],
    description: str,
) -> int:
    if not start or not end or end < start:
        raise PersistentProtocolError(
            f"{description} is missing valid timestamps needed for assignment"
        )
    matches = [
        index
        for index, (window_start, window_end) in enumerate(ranges)
        if end >= window_start and start < window_end
    ]
    if len(matches) != 1:
        reason = "overlaps action intervals" if matches else "is unassignable"
        raise PersistentProtocolError(
            f"{description} {reason}: point=[{start}, {end}], "
            f"actions={list(ranges)}"
        )
    return matches[0]


def _positive_expectations_satisfied(
    action: _ActionWindow,
    window: CapturedWindow,
    metric_boundaries: Sequence[int],
) -> bool:
    scenario = action.scenario
    for expectation in scenario.spans or ():
        if expectation.count is not None and expectation.count > 0:
            if (
                sum(selects(expectation, span) for span in window.spans)
                < expectation.count
            ):
                return False
    if scenario.metrics:
        if not set(scenario.metrics).issubset(window.metric_names):
            return False
        assert action.requested_unix_nano is not None
        # The interval that recorded this action has to be closed, and only
        # this action has recorded anything since the last one settled. An
        # interval closing after the request went out is therefore this
        # action's, whenever the answer reached the driver.
        if not any(
            boundary >= action.requested_unix_nano
            for boundary in metric_boundaries
        ):
            return False
    if scenario.events and not set(scenario.events).issubset(
        window.event_names
    ):
        return False
    return True


def _window_fingerprint(
    window: CapturedWindow, declared_metrics: Sequence[str] | None
) -> object:
    """What a window says about the expectations it is judged on.

    Spans and events in full, every metric name that appeared, and the
    closing timestamps of the declared metrics. An SDK reporting on its own
    queues and exporters changes none of these once an action is done, so a
    window that is otherwise finished settles.
    """
    names = frozenset(declared_metrics or ())
    return (
        tuple(
            (
                span.trace_id,
                span.span_id,
                span.name,
                span.kind,
                span.start_time_unix_nano,
                span.end_time_unix_nano,
            )
            for span in window.spans
        ),
        tuple(sorted(window.event_names)),
        tuple(sorted(set(window.metric_names))),
        tuple(sorted(_metric_point_ends(window, names))) if names else (),
    )


def _metric_point_ends(
    window: CapturedWindow, names: frozenset[str]
) -> list[int]:
    """The closing timestamps of ``names``, ignoring instant snapshots."""

    ends: list[int] = []
    for item in window.exports:
        request = item.request
        if not isinstance(
            request, metrics_service_pb2.ExportMetricsServiceRequest
        ):
            continue
        for resource in request.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    if names and metric.name not in names:
                        continue
                    if self_monitoring(scope.scope.name, metric.name):
                        continue
                    data_name = metric.WhichOneof("data")
                    if data_name is None:
                        continue
                    data = getattr(metric, data_name)
                    if _reports_a_snapshot(data_name, data):
                        continue
                    ends.extend(
                        point.time_unix_nano for point in data.data_points
                    )
    return ends


def _validate_message(
    document: Mapping[str, object], record_type: str, sequence: int
) -> None:
    _validate_envelope(document, sequence)
    if document["type"] != record_type:
        raise PersistentProtocolError(
            f"expected {record_type} sequence {sequence}, got "
            f"{document['type']!r}"
        )


def _exchange_stamps(message: _Message) -> tuple[int, int]:
    """When the driver sent an exchange and when it saw the answer.

    Both come from the driver's own clock. The runner reads a record some
    time after it was written, and the answer can reach the driver later
    than the instrumentation recorded what it measured, so neither instant
    can be recovered from the moment the record arrives.
    """
    stamps: list[int] = []
    for name in ("started_unix_nano", "completed_unix_nano"):
        value = message.document.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise PersistentProtocolError(
                f"protocol record is missing a positive integer {name}: "
                f"{message.line}"
            )
        stamps.append(value)
    started, completed = stamps
    if completed < started:
        raise PersistentProtocolError(
            f"protocol record ends before it starts: {message.line}"
        )
    return started, completed


def _validate_envelope(document: Mapping[str, object], sequence: int) -> None:
    version = document.get("version")
    record_type = document.get("type")
    actual_sequence = document.get("sequence")
    if version != PROTOCOL_VERSION:
        raise PersistentProtocolError(
            f"expected protocol version {PROTOCOL_VERSION!r}, got {version!r}"
        )
    if not isinstance(record_type, str) or not record_type:
        raise PersistentProtocolError("protocol record type must be a string")
    if (
        not isinstance(actual_sequence, int)
        or isinstance(actual_sequence, bool)
        or actual_sequence != sequence
    ):
        raise PersistentProtocolError(
            f"expected sequence {sequence}, got {actual_sequence!r}"
        )


def _trace_id() -> str:
    while True:
        value = secrets.token_hex(16)
        if value != "0" * 32:
            return value


def _raise_json(value: str) -> Any:
    raise ValueError(f"non-finite JSON value {value}")


def _empty_window(name: str, generation: int) -> CapturedWindow:
    return CapturedWindow(name, generation, (), (), (), ())


def _empty_partition(actions: Sequence[_ActionWindow]) -> _Partition:
    return _Partition(
        _empty_window("readiness", 0),
        tuple(
            _empty_window(action.scenario.name, index + 1)
            for index, action in enumerate(actions)
        ),
        tuple(() for _ in actions),
    )
