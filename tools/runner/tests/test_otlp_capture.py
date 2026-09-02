# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The windowed OTLP capture proxy."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import TracebackType

import grpc
import pytest

from opentelemetry.conformance._otlp_capture import (
    CapturedExport,
    CaptureWindow,
    OtlpCaptureProxy,
    UnexpectedExportsError,
    decode_window,
)
from opentelemetry.proto.collector.logs.v1 import (
    logs_service_pb2,
    logs_service_pb2_grpc,
)
from opentelemetry.proto.collector.metrics.v1 import (
    metrics_service_pb2,
    metrics_service_pb2_grpc,
)
from opentelemetry.proto.collector.trace.v1 import (
    trace_service_pb2,
    trace_service_pb2_grpc,
)
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.proto.trace.v1 import trace_pb2


class _Upstream:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.trace_failure: tuple[grpc.StatusCode, str] | None = None
        self.traces: list[trace_service_pb2.ExportTraceServiceRequest] = []
        self.metrics: list[
            metrics_service_pb2.ExportMetricsServiceRequest
        ] = []
        self.logs: list[logs_service_pb2.ExportLogsServiceRequest] = []
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._server = grpc.server(self._executor)
        trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
            _TraceUpstream(self), self._server
        )
        metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(
            _MetricsUpstream(self), self._server
        )
        logs_service_pb2_grpc.add_LogsServiceServicer_to_server(
            _LogsUpstream(self), self._server
        )
        port = self._server.add_insecure_port("127.0.0.1:0")
        assert port != 0
        self.target = f"127.0.0.1:{port}"

    def __enter__(self) -> _Upstream:
        self._server.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release.set()
        self._server.stop(0).wait()
        self._executor.shutdown()


class _TraceUpstream(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self, upstream: _Upstream) -> None:
        self._upstream = upstream

    def Export(
        self,
        request: trace_service_pb2.ExportTraceServiceRequest,
        context: grpc.ServicerContext,
    ) -> trace_service_pb2.ExportTraceServiceResponse:
        self._upstream.started.set()
        self._upstream.release.wait()
        if self._upstream.trace_failure is not None:
            code, details = self._upstream.trace_failure
            context.abort(code, details)
        self._upstream.traces.append(request)
        return trace_service_pb2.ExportTraceServiceResponse(
            partial_success={"rejected_spans": 1}
        )


class _MetricsUpstream(metrics_service_pb2_grpc.MetricsServiceServicer):
    def __init__(self, upstream: _Upstream) -> None:
        self._upstream = upstream

    def Export(
        self,
        request: metrics_service_pb2.ExportMetricsServiceRequest,
        context: grpc.ServicerContext,
    ) -> metrics_service_pb2.ExportMetricsServiceResponse:
        self._upstream.metrics.append(request)
        return metrics_service_pb2.ExportMetricsServiceResponse(
            partial_success={"rejected_data_points": 2}
        )


class _LogsUpstream(logs_service_pb2_grpc.LogsServiceServicer):
    def __init__(self, upstream: _Upstream) -> None:
        self._upstream = upstream

    def Export(
        self,
        request: logs_service_pb2.ExportLogsServiceRequest,
        context: grpc.ServicerContext,
    ) -> logs_service_pb2.ExportLogsServiceResponse:
        self._upstream.logs.append(request)
        return logs_service_pb2.ExportLogsServiceResponse(
            partial_success={"rejected_log_records": 3}
        )


def _clients(
    target: str,
) -> tuple[
    grpc.Channel,
    trace_service_pb2_grpc.TraceServiceStub,
    metrics_service_pb2_grpc.MetricsServiceStub,
    logs_service_pb2_grpc.LogsServiceStub,
]:
    channel = grpc.insecure_channel(target)
    return (
        channel,
        trace_service_pb2_grpc.TraceServiceStub(channel),
        metrics_service_pb2_grpc.MetricsServiceStub(channel),
        logs_service_pb2_grpc.LogsServiceStub(channel),
    )


def _requests() -> tuple[
    trace_service_pb2.ExportTraceServiceRequest,
    metrics_service_pb2.ExportMetricsServiceRequest,
    logs_service_pb2.ExportLogsServiceRequest,
]:
    resource = resource_pb2.Resource(
        attributes=[
            common_pb2.KeyValue(
                key="service.name",
                value=common_pb2.AnyValue(string_value="checkout"),
            )
        ]
    )
    scope = common_pb2.InstrumentationScope(name="example", version="1.2.3")
    trace_id = bytes.fromhex("00112233445566778899aabbccddeeff")
    span_id = bytes.fromhex("0011223344556677")
    trace = trace_service_pb2.ExportTraceServiceRequest(
        resource_spans=[
            trace_pb2.ResourceSpans(
                resource=resource,
                scope_spans=[
                    trace_pb2.ScopeSpans(
                        scope=scope,
                        spans=[
                            trace_pb2.Span(
                                trace_id=trace_id,
                                span_id=span_id,
                                parent_span_id=b"\x10" * 8,
                                name="GET /cart",
                                kind=trace_pb2.Span.SPAN_KIND_CLIENT,
                                start_time_unix_nano=101,
                                end_time_unix_nano=202,
                                attributes=[
                                    common_pb2.KeyValue(
                                        key="http.request.method",
                                        value=common_pb2.AnyValue(
                                            string_value="GET"
                                        ),
                                    ),
                                    common_pb2.KeyValue(
                                        key="server.port",
                                        value=common_pb2.AnyValue(
                                            string_value="malformed"
                                        ),
                                    ),
                                    common_pb2.KeyValue(
                                        key="finish.reasons",
                                        value=common_pb2.AnyValue(
                                            array_value=common_pb2.ArrayValue(
                                                values=[
                                                    common_pb2.AnyValue(
                                                        string_value="stop"
                                                    )
                                                ]
                                            )
                                        ),
                                    ),
                                    common_pb2.KeyValue(
                                        key="request.options",
                                        value=common_pb2.AnyValue(
                                            kvlist_value=common_pb2.KeyValueList(
                                                values=[
                                                    common_pb2.KeyValue(
                                                        key="stream",
                                                        value=common_pb2.AnyValue(
                                                            bool_value=True
                                                        ),
                                                    )
                                                ]
                                            )
                                        ),
                                    ),
                                ],
                                events=[
                                    trace_pb2.Span.Event(name="span.only")
                                ],
                            )
                        ],
                    )
                ],
            )
        ]
    )
    metrics = metrics_service_pb2.ExportMetricsServiceRequest(
        resource_metrics=[
            metrics_pb2.ResourceMetrics(
                resource=resource,
                scope_metrics=[
                    metrics_pb2.ScopeMetrics(
                        scope=scope,
                        metrics=[
                            metrics_pb2.Metric(
                                name="requests",
                                sum=metrics_pb2.Sum(
                                    aggregation_temporality=(
                                        metrics_pb2.AGGREGATION_TEMPORALITY_DELTA
                                    ),
                                    data_points=[
                                        metrics_pb2.NumberDataPoint(
                                            start_time_unix_nano=303,
                                            time_unix_nano=404,
                                            as_int=5,
                                        )
                                    ],
                                ),
                            ),
                            metrics_pb2.Metric(name="empty"),
                        ],
                    )
                ],
            )
        ]
    )
    logs = logs_service_pb2.ExportLogsServiceRequest(
        resource_logs=[
            logs_pb2.ResourceLogs(
                resource=resource,
                scope_logs=[
                    logs_pb2.ScopeLogs(
                        scope=scope,
                        log_records=[
                            logs_pb2.LogRecord(
                                time_unix_nano=505,
                                observed_time_unix_nano=606,
                                trace_id=trace_id,
                                span_id=span_id,
                                body=common_pb2.AnyValue(string_value="done"),
                                event_name="cart.completed",
                            )
                        ],
                    )
                ],
            )
        ]
    )
    return trace, metrics, logs


def test_all_export_services_share_one_endpoint_and_forward_responses() -> (
    None
):
    trace, metrics, logs = _requests()
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        window = capture.open_window("checkout")
        channel, trace_client, metrics_client, logs_client = _clients(
            capture.target
        )
        try:
            trace_response = trace_client.Export(trace)
            metrics_response = metrics_client.Export(metrics)
            logs_response = logs_client.Export(logs)
        finally:
            channel.close()
        captured = capture.close_window(window, timeout=1)

    assert capture.endpoint == f"http://{capture.target}"
    assert trace_response.partial_success.rejected_spans == 1
    assert metrics_response.partial_success.rejected_data_points == 2
    assert logs_response.partial_success.rejected_log_records == 3
    assert upstream.traces == [trace]
    assert upstream.metrics == [metrics]
    assert upstream.logs == [logs]
    assert [item.signal for item in captured.exports] == [
        "traces",
        "metrics",
        "logs",
    ]


def test_raw_protobuf_data_is_retained_in_its_window() -> None:
    requests = _requests()
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        window = capture.open_window("raw-data")
        channel, traces, metrics, logs = _clients(capture.target)
        try:
            traces.Export(requests[0])
            metrics.Export(requests[1])
            logs.Export(requests[2])
        finally:
            channel.close()
        captured = capture.close_window(window, timeout=1)

    for item, request in zip(captured.exports, requests):
        assert item.request is not request
        assert item.request.SerializeToString() == request.SerializeToString()

    span = (
        captured.exports[0].request.resource_spans[0].scope_spans[0].spans[0]
    )
    point = (
        captured.exports[1]
        .request.resource_metrics[0]
        .scope_metrics[0]
        .metrics[0]
        .sum.data_points[0]
    )
    log = (
        captured.exports[2]
        .request.resource_logs[0]
        .scope_logs[0]
        .log_records[0]
    )
    assert span.trace_id == bytes.fromhex("00112233445566778899aabbccddeeff")
    assert (span.start_time_unix_nano, span.end_time_unix_nano) == (101, 202)
    assert point.time_unix_nano == 404
    assert (
        captured.exports[1]
        .request.resource_metrics[0]
        .scope_metrics[0]
        .metrics[0]
        .sum.aggregation_temporality
        == metrics_pb2.AGGREGATION_TEMPORALITY_DELTA
    )
    assert log.observed_time_unix_nano == 606
    assert captured.exports[0].request.resource_spans[0].resource.attributes[
        0
    ].key == ("service.name")
    assert (
        captured.exports[2].request.resource_logs[0].scope_logs[0].scope.name
        == "example"
    )
    (decoded,) = captured.spans
    assert decoded.name == "GET /cart"
    assert decoded.kind == "SPAN_KIND_CLIENT"
    assert decoded.attributes == {
        "finish.reasons": ["stop"],
        "http.request.method": "GET",
        "request.options": {"stream": True},
        "server.port": "malformed",
    }
    assert decoded.trace_id == bytes.fromhex(
        "00112233445566778899aabbccddeeff"
    )
    assert decoded.span_id == bytes.fromhex("0011223344556677")
    assert decoded.parent_span_id == b"\x10" * 8
    assert (decoded.start_time_unix_nano, decoded.end_time_unix_nano) == (
        101,
        202,
    )
    assert captured.metric_names == ("requests", "empty")
    assert captured.event_names == ("cart.completed",)


def test_sdk_self_monitoring_metrics_are_not_scenario_telemetry() -> None:
    request = metrics_service_pb2.ExportMetricsServiceRequest(
        resource_metrics=[
            metrics_pb2.ResourceMetrics(
                scope_metrics=[
                    metrics_pb2.ScopeMetrics(
                        scope=common_pb2.InstrumentationScope(
                            name="io.opentelemetry.sdk.trace"
                        ),
                        metrics=[metrics_pb2.Metric(name="queueSize")],
                    ),
                    metrics_pb2.ScopeMetrics(
                        scope=common_pb2.InstrumentationScope(
                            name="io.opentelemetry.exporters.otlp-grpc"
                        ),
                        metrics=[
                            metrics_pb2.Metric(name="otlp.exporter.seen")
                        ],
                    ),
                    metrics_pb2.ScopeMetrics(
                        scope=common_pb2.InstrumentationScope(name="wsgi"),
                        metrics=[
                            metrics_pb2.Metric(name="otel.sdk.span.live"),
                            metrics_pb2.Metric(
                                name="http.server.request.duration"
                            ),
                        ],
                    ),
                ]
            )
        ]
    )

    window = decode_window(
        CaptureWindow("self-monitoring", 1),
        (CapturedExport("metrics", request),),
    )

    assert window.metric_names == ("http.server.request.duration",)
    assert len(window.exports) == 1


def test_named_window_generations_do_not_mix_requests() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        channel, client, _, _ = _clients(capture.target)
        try:
            first = capture.open_window("same-name")
            client.Export(trace)
            first_requests = capture.close_window(first, timeout=1)
            second = capture.open_window("same-name")
            client.Export(trace)
            second_requests = capture.close_window(second, timeout=1)
        finally:
            channel.close()

    assert second.generation == first.generation + 1
    assert capture.requests(first) == first_requests.exports
    assert capture.requests(second) == second_requests.exports
    assert first_requests is not second_requests


def test_export_does_not_acknowledge_before_forwarding_completes() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        upstream.release.clear()
        window = capture.open_window("blocking")
        channel, client, _, _ = _clients(capture.target)
        future = client.Export.future(trace)
        assert upstream.started.wait(1)
        assert not future.done()
        with pytest.raises(TimeoutError, match="OTLP capture service"):
            capture.drain(timeout=0.01)
        upstream.release.set()
        assert future.result(timeout=1).partial_success.rejected_spans == 1
        capture.drain(timeout=1)
        assert len(capture.close_window(window, timeout=1).exports) == 1
        channel.close()


def test_capture_snapshot_notifies_ingress_and_in_flight_drain() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        upstream.release.clear()
        changed = Event()
        capture.set_change_notifier(changed.set)
        window = capture.open_window("notifications")
        channel, client, _, _ = _clients(capture.target)
        future = client.Export.future(trace)
        assert changed.wait(1)
        ingress = capture.snapshot(window)
        assert len(ingress.exports) == 1
        assert ingress.in_flight == 1

        changed.clear()
        upstream.release.set()
        future.result(timeout=1)
        assert changed.wait(1)
        drained = capture.snapshot(window)
        assert drained.in_flight == 0
        assert drained.revision > ingress.revision
        capture.close_window(window, timeout=1)
        channel.close()


def test_close_window_drains_calls_assigned_before_deactivation() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        upstream.release.clear()
        window = capture.open_window("drain")
        channel, client, _, _ = _clients(capture.target)
        future = client.Export.future(trace)
        assert upstream.started.wait(1)
        with pytest.raises(TimeoutError, match="capture window 'drain'"):
            capture.close_window(window, timeout=0.01)
        assert capture.active_window is None
        upstream.release.set()
        future.result(timeout=1)
        capture.drain(timeout=1)
        assert len(capture.requests(window)) == 1
        channel.close()


def test_requests_without_a_window_are_forwarded_but_quarantined() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        channel, client, _, _ = _clients(capture.target)
        try:
            response = client.Export(trace)
        finally:
            channel.close()

    assert response.partial_success.rejected_spans == 1
    assert upstream.traces == [trace]
    assert len(capture.quarantined_requests) == 1
    with pytest.raises(
        UnexpectedExportsError,
        match="without an active capture window: traces=1",
    ):
        capture.raise_for_quarantined()


def test_close_ingress_settles_an_export_admitted_at_the_boundary() -> None:
    """Ingress is not closed while an admitted call is still being handled.

    A call the transport accepted is the one a caller must not read past: it
    is quarantined only when its handler reaches the proxy, so a quarantine
    read that does not wait for it would leave it in no report at all.
    """
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        upstream.release.clear()
        channel, client, _, _ = _clients(capture.target)
        future = client.Export.future(trace)
        assert upstream.started.wait(5)

        with pytest.raises(TimeoutError, match="OTLP capture service"):
            capture.close_ingress(timeout=0.5)

        upstream.release.set()
        try:
            future.result(timeout=5)
        except grpc.RpcError:
            # The blocked call may have been cut short by the grace above;
            # what it left in the proxy is what this is about.
            pass
        capture.close_ingress(timeout=30)

        assert len(capture.quarantined_requests) == 1
        with pytest.raises(
            UnexpectedExportsError,
            match="without an active capture window: traces=1",
        ):
            capture.raise_for_quarantined()
        channel.close()


def test_closed_ingress_refuses_further_exports() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        capture.close_ingress(timeout=30)
        channel, client, _, _ = _clients(capture.target)
        try:
            with pytest.raises(grpc.RpcError) as raised:
                client.Export(trace, timeout=5)
        finally:
            channel.close()

    assert raised.value.code() is grpc.StatusCode.UNAVAILABLE
    assert not capture.quarantined_requests
    assert upstream.traces == []
    with pytest.raises(RuntimeError, match="closed"):
        capture.open_window("after")


def test_forwarding_failure_preserves_status_and_is_still_captured() -> None:
    trace = _requests()[0]
    with _Upstream() as upstream, OtlpCaptureProxy(upstream.target) as capture:
        upstream.trace_failure = (grpc.StatusCode.RESOURCE_EXHAUSTED, "full")
        window = capture.open_window("failure")
        channel, client, _, _ = _clients(capture.target)
        try:
            with pytest.raises(grpc.RpcError) as raised:
                client.Export(trace)
        finally:
            channel.close()
        captured = capture.close_window(window, timeout=1)

    assert raised.value.code() is grpc.StatusCode.RESOURCE_EXHAUSTED
    assert raised.value.details() == "full"
    assert len(captured.exports) == 1
