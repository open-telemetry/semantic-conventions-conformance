# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""In-pipeline OTLP tee: captures raw trace spans (with IDs and timestamps
intact) while transparently forwarding every OTLP export unchanged to
weaver, so its coverage report is unaffected by capture.

Weaver's ``registry live-check`` strips trace/span/parent IDs and timestamps
from its own report — it only emits per-attribute coverage stats. This tee
sits between the scenario under test and weaver's real gRPC port, replaying
each request byte-for-byte after recording it, so a waterfall viewer can
reconstruct actual parent/child nesting and timing.
"""

from __future__ import annotations

import json
import threading
from concurrent import futures
from pathlib import Path

import grpc
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2_grpc
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc


def _decode_events(events) -> list[dict[str, object]]:
    return [
        {
            "time_unix_nano": event.time_unix_nano,
            "name": event.name,
            "attributes": _decode_attributes(event.attributes),
            "dropped_attributes_count": event.dropped_attributes_count,
        }
        for event in events
    ]


def _decode_links(links) -> list[dict[str, object]]:
    return [
        {
            "trace_id": link.trace_id.hex(),
            "span_id": link.span_id.hex(),
            "trace_state": link.trace_state,
            "attributes": _decode_attributes(link.attributes),
            "dropped_attributes_count": link.dropped_attributes_count,
        }
        for link in links
    ]


def _decode_status(status) -> dict[str, object]:
    return {
        "message": status.message,
        "code": status.code,
    }


def _decode_attributes(attrs) -> dict[str, object]:
    decoded: dict[str, object] = {}
    for attr in attrs:
        value = attr.value
        if value.HasField("string_value"):
            decoded[attr.key] = value.string_value
        elif value.HasField("int_value"):
            decoded[attr.key] = value.int_value
        elif value.HasField("double_value"):
            decoded[attr.key] = value.double_value
        elif value.HasField("bool_value"):
            decoded[attr.key] = value.bool_value
        else:
            decoded[attr.key] = MessageToDict(value)
    return decoded


def _decode_resource_attributes(attrs) -> dict[str, object]:
    """Decode resource attributes, redacting fields that leak local machine
    details (executable path, full command line) from captured traces."""
    decoded = _decode_attributes(attrs)
    if "process.executable.path" in decoded:
        decoded["process.executable.path"] = "REDACTED"
    if "process.command_line" in decoded:
        decoded["process.command_line"] = "REDACTED"
    if "process.command_args" in decoded:
        arg_count = 0
        for attr in attrs:
            if attr.key == "process.command_args" and attr.value.HasField(
                "array_value"
            ):
                arg_count = len(attr.value.array_value.values)
                break
        decoded["process.command_args"] = f"{arg_count} REDACTED ARGS"
    return decoded


class _TraceCaptureServicer(trace_service_pb2_grpc.TraceServiceServicer):
    """Records raw spans, then forwards the untouched request to weaver."""

    def __init__(
        self,
        forward_stub: trace_service_pb2_grpc.TraceServiceStub,
        out_path: Path,
    ) -> None:
        self._forward_stub = forward_stub
        self._out_path = out_path
        self._lock = threading.Lock()

    def Export(self, request, context):
        lines = []
        for resource_spans in request.resource_spans:
            resource_attributes = _decode_resource_attributes(
                resource_spans.resource.attributes
            )
            resource_dropped_attributes_count = (
                resource_spans.resource.dropped_attributes_count
            )
            for scope_spans in resource_spans.scope_spans:
                scope_name = scope_spans.scope.name
                for span in scope_spans.spans:
                    lines.append(
                        json.dumps(
                            {
                                "trace_id": span.trace_id.hex(),
                                "span_id": span.span_id.hex(),
                                "trace_state": span.trace_state,
                                "parent_span_id": span.parent_span_id.hex()
                                if span.parent_span_id
                                else None,
                                "name": span.name,
                                "kind": span.kind,
                                "scope": scope_name,
                                "start_time_unix_nano": span.start_time_unix_nano,
                                "end_time_unix_nano": span.end_time_unix_nano,
                                "attributes": _decode_attributes(
                                    span.attributes
                                ),
                                "dropped_attributes_count": span.dropped_attributes_count,
                                "events": _decode_events(span.events),
                                "dropped_events_count": span.dropped_events_count,
                                "links": _decode_links(span.links),
                                "dropped_links_count": span.dropped_links_count,
                                "status": _decode_status(span.status),
                                "resource_attributes": resource_attributes,
                                "resource_dropped_attributes_count": resource_dropped_attributes_count,
                            }
                        )
                    )

        if lines:
            # One JSON object per line (JSONL), appended as each export
            # arrives, rather than rewriting a single growing array on every
            # call — cheaper, and a reader can stream it as spans come in.
            with self._lock, self._out_path.open("a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

        # Byte-for-byte replay: forward the exact same request so weaver's
        # coverage report is unaffected by the fact that capture happened.
        return self._forward_stub.Export(request, timeout=10)


class _PassthroughMetricsServicer(
    metrics_service_pb2_grpc.MetricsServiceServicer
):
    def __init__(
        self, forward_stub: metrics_service_pb2_grpc.MetricsServiceStub
    ) -> None:
        self._forward_stub = forward_stub

    def Export(self, request, context):
        return self._forward_stub.Export(request, timeout=10)


class _PassthroughLogsServicer(logs_service_pb2_grpc.LogsServiceServicer):
    def __init__(
        self, forward_stub: logs_service_pb2_grpc.LogsServiceStub
    ) -> None:
        self._forward_stub = forward_stub

    def Export(self, request, context):
        return self._forward_stub.Export(request, timeout=10)


class SpanCaptureBridge:
    """OTLP gRPC tee: captures raw trace spans to disk, then forwards every
    export (traces, metrics, logs) unchanged to a downstream collector
    (weaver).
    """

    def __init__(self, forward_endpoint: str, out_path: Path) -> None:
        self._out_path = out_path
        self._channel = grpc.insecure_channel(
            forward_endpoint.removeprefix("http://").removeprefix(
                "https://"
            )
        )
        self._port: int | None = None
        self._server: grpc.Server | None = None

    @property
    def endpoint(self) -> str:
        assert self._port is not None, "call start() first"
        return f"http://localhost:{self._port}"

    def start(self) -> None:
        self._out_path.parent.mkdir(parents=True, exist_ok=True)
        # Export appends; truncate first so a rerun doesn't tack new spans
        # onto a previous run's leftover file.
        self._out_path.write_text("", encoding="utf-8")
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
            _TraceCaptureServicer(
                trace_service_pb2_grpc.TraceServiceStub(self._channel),
                self._out_path,
            ),
            server,
        )
        metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(
            _PassthroughMetricsServicer(
                metrics_service_pb2_grpc.MetricsServiceStub(self._channel)
            ),
            server,
        )
        logs_service_pb2_grpc.add_LogsServiceServicer_to_server(
            _PassthroughLogsServicer(
                logs_service_pb2_grpc.LogsServiceStub(self._channel)
            ),
            server,
        )
        # :0 asks the OS for a free port and binds it atomically in one
        # step, unlike probing a port with a throwaway socket and hoping
        # nothing else claims it before this server binds the real one.
        self._port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        self._server = server

    def stop(self) -> None:
        if self._server is not None:
            self._server.stop(grace=5).wait(timeout=10)
            self._server = None
        self._channel.close()
