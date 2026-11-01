# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import cast

import pytest
from otel_conformance_python import _flush_before_shutdown

from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider


class Provider:
    def __init__(self, name: str, events: list[str], result: bool = True):
        self.name = name
        self.events = events
        self.result = result
        self.timeouts: list[int] = []

    def force_flush(self, timeout_millis: int) -> bool:
        self.events.append(self.name)
        self.timeouts.append(timeout_millis)
        return self.result


def providers(
    trace: Provider, metric: Provider, log: Provider
) -> tuple[TracerProvider, MeterProvider, LoggerProvider]:
    return (
        cast(TracerProvider, trace),
        cast(MeterProvider, metric),
        cast(LoggerProvider, log),
    )


def test_traces_and_logs_flush_before_metrics() -> None:
    events: list[str] = []
    trace = Provider("trace", events)
    log = Provider("log", events)
    metric = Provider("metric", events)

    _flush_before_shutdown(providers(trace, metric, log))

    assert events[-1] == "metric"
    assert set(events[:2]) == {"trace", "log"}
    assert all(timeout <= 15_000 for timeout in trace.timeouts + log.timeouts)
    assert metric.timeouts[0] <= log.timeouts[0]


def test_a_trace_or_log_failure_stops_before_metrics() -> None:
    events: list[str] = []
    trace = Provider("trace", events, result=False)
    log = Provider("log", events)
    metric = Provider("metric", events)

    with pytest.raises(RuntimeError, match="trace flush"):
        _flush_before_shutdown(providers(trace, metric, log))

    assert set(events) == {"trace", "log"}


def test_timeout_uses_a_bounded_budget() -> None:
    events: list[str] = []
    trace = Provider("trace", events)
    log = Provider("log", events)
    metric = Provider("metric", events, result=False)

    with pytest.raises(RuntimeError, match="metric flush"):
        _flush_before_shutdown(providers(trace, metric, log), timeout_millis=0)

    assert trace.timeouts == [0]
    assert log.timeouts == [0]
    assert metric.timeouts == [0]
