# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The in-process OTLP/HTTP protobuf to OTLP/gRPC bridge."""

from __future__ import annotations

import gzip
import http.client
import urllib.request
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http import HTTPStatus

import grpc
import pytest
from google.protobuf.message import Message

from opentelemetry.conformance._otlp_http import OtlpHttpBridge
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.logs.v1.logs_service_pb2_grpc import (
    LogsServiceServicer,
    add_LogsServiceServicer_to_server,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2_grpc import (
    MetricsServiceServicer,
    add_MetricsServiceServicer_to_server,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc import (
    TraceServiceServicer,
    add_TraceServiceServicer_to_server,
)


@dataclass
class _Received:
    traces: list[ExportTraceServiceRequest] = field(default_factory=list)
    metrics: list[ExportMetricsServiceRequest] = field(default_factory=list)
    logs: list[ExportLogsServiceRequest] = field(default_factory=list)
    fail: bool = False


class _Traces(TraceServiceServicer):
    def __init__(self, received: _Received) -> None:
        self._received = received

    def Export(  # noqa: N802
        self,
        request: ExportTraceServiceRequest,
        context: grpc.ServicerContext,
    ) -> ExportTraceServiceResponse:
        if self._received.fail:
            context.abort(grpc.StatusCode.INTERNAL, "collector rejected traces")
        self._received.traces.append(request)
        return ExportTraceServiceResponse()


class _Metrics(MetricsServiceServicer):
    def __init__(self, received: _Received) -> None:
        self._received = received

    def Export(  # noqa: N802
        self,
        request: ExportMetricsServiceRequest,
        context: grpc.ServicerContext,
    ) -> ExportMetricsServiceResponse:
        self._received.metrics.append(request)
        return ExportMetricsServiceResponse()


class _Logs(LogsServiceServicer):
    def __init__(self, received: _Received) -> None:
        self._received = received

    def Export(  # noqa: N802
        self,
        request: ExportLogsServiceRequest,
        context: grpc.ServicerContext,
    ) -> ExportLogsServiceResponse:
        self._received.logs.append(request)
        return ExportLogsServiceResponse()


@pytest.fixture
def collector() -> Generator[tuple[str, _Received], None, None]:
    received = _Received()
    server = grpc.server(ThreadPoolExecutor(max_workers=3))
    add_TraceServiceServicer_to_server(_Traces(received), server)
    add_MetricsServiceServicer_to_server(_Metrics(received), server)
    add_LogsServiceServicer_to_server(_Logs(received), server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"http://127.0.0.1:{port}", received
    finally:
        server.stop(grace=None).wait()


def _post(
    bridge: OtlpHttpBridge,
    path: str,
    body: bytes,
    *,
    content_type: str = "application/x-protobuf",
    encoding: str | None = None,
) -> tuple[int, bytes, str | None]:
    connection = http.client.HTTPConnection(
        "127.0.0.1",
        int(bridge.url.rsplit(":", 1)[1]),
        timeout=5,
    )
    headers = {"Content-Type": content_type}
    if encoding is not None:
        headers["Content-Encoding"] = encoding
    connection.request("POST", path, body=body, headers=headers)
    response = connection.getresponse()
    result = (
        response.status,
        response.read(),
        response.getheader("Content-Type"),
    )
    connection.close()
    return result


@pytest.mark.parametrize(
    ("path", "payload", "attribute"),
    [
        pytest.param(
            "/v1/traces",
            ExportTraceServiceRequest(),
            "traces",
            id="traces",
        ),
        pytest.param(
            "/v1/metrics",
            ExportMetricsServiceRequest(),
            "metrics",
            id="metrics",
        ),
        pytest.param(
            "/v1/logs",
            ExportLogsServiceRequest(),
            "logs",
            id="logs",
        ),
    ],
)
def test_forwards_each_otlp_signal(
    collector: tuple[str, _Received],
    path: str,
    payload: Message,
    attribute: str,
) -> None:
    endpoint, received = collector
    with OtlpHttpBridge(endpoint) as bridge:
        status, body, content_type = _post(
            bridge, path, payload.SerializeToString()
        )

    assert status == HTTPStatus.OK
    assert body == b""
    assert content_type == "application/x-protobuf"
    assert len(getattr(received, attribute)) == 1


def test_accepts_gzip_bodies(collector: tuple[str, _Received]) -> None:
    endpoint, received = collector
    request = ExportMetricsServiceRequest()
    request.resource_metrics.add()

    with OtlpHttpBridge(endpoint) as bridge:
        status, _, _ = _post(
            bridge,
            "/v1/metrics",
            gzip.compress(request.SerializeToString()),
            encoding="gzip",
        )

    assert status == HTTPStatus.OK
    assert len(received.metrics[0].resource_metrics) == 1


@pytest.mark.parametrize(
    ("path", "body", "content_type", "encoding", "status", "message"),
    [
        pytest.param(
            "/v1/unknown",
            b"",
            "application/x-protobuf",
            None,
            HTTPStatus.NOT_FOUND,
            b"unknown OTLP endpoint",
            id="endpoint",
        ),
        pytest.param(
            "/v1/traces",
            b"",
            "application/json",
            None,
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            b"content type must be application/x-protobuf",
            id="content-type",
        ),
        pytest.param(
            "/v1/traces",
            b"",
            "application/x-protobuf",
            "br",
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            b"unsupported content encoding",
            id="content-encoding",
        ),
        pytest.param(
            "/v1/traces",
            b"not gzip",
            "application/x-protobuf",
            "gzip",
            HTTPStatus.BAD_REQUEST,
            b"invalid gzip body",
            id="gzip",
        ),
        pytest.param(
            "/v1/traces",
            b"\x80",
            "application/x-protobuf",
            None,
            HTTPStatus.BAD_REQUEST,
            b"invalid protobuf payload",
            id="protobuf",
        ),
    ],
)
def test_rejects_invalid_requests(
    collector: tuple[str, _Received],
    path: str,
    body: bytes,
    content_type: str,
    encoding: str | None,
    status: HTTPStatus,
    message: bytes,
) -> None:
    endpoint, _ = collector
    with OtlpHttpBridge(endpoint) as bridge:
        actual, response, _ = _post(
            bridge,
            path,
            body,
            content_type=content_type,
            encoding=encoding,
        )

    assert actual == status
    assert message in response


@pytest.mark.parametrize(
    ("content_length", "status", "message"),
    [
        pytest.param(None, HTTPStatus.LENGTH_REQUIRED, b"required", id="missing"),
        pytest.param(
            "invalid", HTTPStatus.BAD_REQUEST, b"invalid", id="malformed"
        ),
        pytest.param("-1", HTTPStatus.BAD_REQUEST, b"invalid", id="negative"),
        pytest.param(
            str(64 * 1024 * 1024 + 1),
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            b"exceeds",
            id="too-large",
        ),
    ],
)
def test_rejects_invalid_content_length(
    collector: tuple[str, _Received],
    content_length: str | None,
    status: HTTPStatus,
    message: bytes,
) -> None:
    endpoint, _ = collector
    with OtlpHttpBridge(endpoint) as bridge:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            int(bridge.url.rsplit(":", 1)[1]),
            timeout=5,
        )
        connection.putrequest("POST", "/v1/traces")
        connection.putheader("Content-Type", "application/x-protobuf")
        if content_length is not None:
            connection.putheader("Content-Length", content_length)
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
        connection.close()

    assert response.status == status
    assert message in body


def test_reports_upstream_failures(
    collector: tuple[str, _Received],
) -> None:
    endpoint, received = collector
    received.fail = True

    with OtlpHttpBridge(endpoint) as bridge:
        status, body, _ = _post(bridge, "/v1/traces", b"")

    assert status == HTTPStatus.BAD_GATEWAY
    assert b"OTLP/gRPC upstream failed: collector rejected traces" in body


@pytest.mark.parametrize(
    "endpoint",
    [
        "localhost:4317",
        "https://localhost:4317",
        "http://localhost",
        "http://user@localhost:4317",
        "http://localhost:4317/v1/traces",
    ],
)
def test_rejects_invalid_upstream_endpoints(endpoint: str) -> None:
    with pytest.raises(ValueError, match="invalid OTLP/gRPC endpoint"):
        OtlpHttpBridge(endpoint)


def test_start_health_and_close_are_deterministic(
    collector: tuple[str, _Received],
) -> None:
    endpoint, _ = collector
    bridge = OtlpHttpBridge(endpoint)
    assert bridge.start() is bridge
    assert bridge.start() is bridge

    with urllib.request.urlopen(f"{bridge.url}/health") as response:
        assert response.status == HTTPStatus.OK
        assert response.read() == b"ok\n"

    bridge.close()
    bridge.close()
    with pytest.raises(RuntimeError, match="closed"):
        bridge.start()
