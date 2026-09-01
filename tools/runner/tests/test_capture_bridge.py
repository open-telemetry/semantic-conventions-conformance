# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The OTLP tee that captures raw spans while forwarding them unchanged."""

from __future__ import annotations

import json
from concurrent import futures
from pathlib import Path

import grpc
import pytest
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2 as trace_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.proto.trace.v1 import trace_pb2 as otel_trace_pb2

from opentelemetry.conformance._capture_bridge import SpanCaptureBridge


class _RecordingTraceServicer(trace_service_pb2_grpc.TraceServiceServicer):
    """Stands in for weaver: records every request it receives."""

    def __init__(self) -> None:
        self.requests: list[trace_pb2.ExportTraceServiceRequest] = []

    def Export(self, request, context):
        self.requests.append(request)
        return trace_pb2.ExportTraceServiceResponse()


@pytest.fixture
def fake_collector():
    servicer = _RecordingTraceServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
        servicer, server
    )
    # :0 asks the OS for a free port and binds it atomically, unlike probing
    # with a throwaway socket that could lose the port to another process
    # before this server binds it for real.
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield servicer, f"http://localhost:{port}"
    finally:
        server.stop(grace=0).wait(timeout=5)


def _string_attr(key: str, value: str) -> common_pb2.KeyValue:
    return common_pb2.KeyValue(
        key=key, value=common_pb2.AnyValue(string_value=value)
    )


def _build_request(
    *, executable_path: str | None = None, command_args: list[str] | None = None
) -> trace_pb2.ExportTraceServiceRequest:
    resource_attributes = []
    if executable_path is not None:
        resource_attributes.append(
            _string_attr("process.executable.path", executable_path)
        )
    if command_args is not None:
        resource_attributes.append(
            common_pb2.KeyValue(
                key="process.command_args",
                value=common_pb2.AnyValue(
                    array_value=common_pb2.ArrayValue(
                        values=[
                            common_pb2.AnyValue(string_value=arg)
                            for arg in command_args
                        ]
                    )
                ),
            )
        )
    span = otel_trace_pb2.Span(
        trace_id=bytes.fromhex("00" * 15 + "01"),
        span_id=bytes.fromhex("00" * 7 + "01"),
        name="do-work",
        kind=otel_trace_pb2.Span.SPAN_KIND_INTERNAL,
        start_time_unix_nano=1_000,
        end_time_unix_nano=2_000,
        attributes=[_string_attr("gen_ai.system", "openai")],
    )
    return trace_pb2.ExportTraceServiceRequest(
        resource_spans=[
            otel_trace_pb2.ResourceSpans(
                resource=resource_pb2.Resource(
                    attributes=resource_attributes
                ),
                scope_spans=[
                    otel_trace_pb2.ScopeSpans(
                        scope=common_pb2.InstrumentationScope(name="test"),
                        spans=[span],
                    )
                ],
            )
        ]
    )


def _export(endpoint: str, request: trace_pb2.ExportTraceServiceRequest) -> None:
    target = endpoint.removeprefix("http://").removeprefix("https://")
    with grpc.insecure_channel(target) as channel:
        stub = trace_service_pb2_grpc.TraceServiceStub(channel)
        stub.Export(request, timeout=5)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_forwards_requests_unchanged(fake_collector, tmp_path: Path) -> None:
    servicer, collector_endpoint = fake_collector
    bridge = SpanCaptureBridge(
        forward_endpoint=collector_endpoint, out_path=tmp_path / "out.spans.jsonl"
    )
    bridge.start()
    try:
        request = _build_request()
        _export(bridge.endpoint, request)
    finally:
        bridge.stop()

    assert len(servicer.requests) == 1
    assert servicer.requests[0] == request


def test_captures_decoded_spans(fake_collector, tmp_path: Path) -> None:
    _, collector_endpoint = fake_collector
    out_path = tmp_path / "out.spans.jsonl"
    bridge = SpanCaptureBridge(
        forward_endpoint=collector_endpoint, out_path=out_path
    )
    bridge.start()
    try:
        _export(bridge.endpoint, _build_request())
    finally:
        bridge.stop()

    spans = _read_jsonl(out_path)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "do-work"
    assert span["trace_id"] == "00" * 15 + "01"
    assert span["span_id"] == "00" * 7 + "01"
    assert span["start_time_unix_nano"] == 1_000
    assert span["end_time_unix_nano"] == 2_000
    assert span["attributes"]["gen_ai.system"] == "openai"


def test_appends_across_exports(fake_collector, tmp_path: Path) -> None:
    _, collector_endpoint = fake_collector
    out_path = tmp_path / "out.spans.jsonl"
    bridge = SpanCaptureBridge(
        forward_endpoint=collector_endpoint, out_path=out_path
    )
    bridge.start()
    try:
        _export(bridge.endpoint, _build_request())
        _export(bridge.endpoint, _build_request())
    finally:
        bridge.stop()

    spans = _read_jsonl(out_path)
    assert len(spans) == 2


def test_redacts_process_details(fake_collector, tmp_path: Path) -> None:
    _, collector_endpoint = fake_collector
    out_path = tmp_path / "out.spans.jsonl"
    bridge = SpanCaptureBridge(
        forward_endpoint=collector_endpoint, out_path=out_path
    )
    bridge.start()
    try:
        request = _build_request(
            executable_path="/Users/me/secret/python",
            command_args=["python", "-m", "scenario"],
        )
        _export(bridge.endpoint, request)
    finally:
        bridge.stop()

    spans = _read_jsonl(out_path)
    resource_attributes = spans[0]["resource_attributes"]
    assert resource_attributes["process.executable.path"] == "REDACTED"
    assert resource_attributes["process.command_args"] == "3 REDACTED ARGS"
