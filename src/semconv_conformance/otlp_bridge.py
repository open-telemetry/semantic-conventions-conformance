# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Small OTLP HTTP-to-gRPC bridge used by tests that cannot export OTLP gRPC directly."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse

import grpc
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2, logs_service_pb2_grpc
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2, metrics_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc


class OtlpHttpBridge:
    """Expose OTLP HTTP protobuf endpoints and forward requests to a gRPC collector."""

    def __init__(self, listen_port: int, collector_endpoint: str) -> None:
        parsed = urlparse(collector_endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid collector endpoint: {collector_endpoint}")

        self.endpoint = f"http://127.0.0.1:{listen_port}"
        self.health_url = f"{self.endpoint}/health"
        self._channel = grpc.insecure_channel(parsed.netloc)
        self._trace_stub = trace_service_pb2_grpc.TraceServiceStub(self._channel)
        self._metric_stub = metrics_service_pb2_grpc.MetricsServiceStub(self._channel)
        self._logs_stub = logs_service_pb2_grpc.LogsServiceStub(self._channel)
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._listen_port = listen_port

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def handle(self) -> None:
                try:
                    super().handle()
                except ConnectionResetError:
                    # Noisy and expected: instrumentation clients routinely
                    # close the connection immediately after an export
                    # without waiting for us to finish reading the request.
                    return

            def do_GET(self) -> None:
                if self.path != "/health":
                    self._send_response(HTTPStatus.NOT_FOUND, b"not found")
                    return

                self._send_response(HTTPStatus.OK, b"ok")

            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", "0"))
                payload = self.rfile.read(content_length)

                try:
                    if self.path == "/v1/traces":
                        request = trace_service_pb2.ExportTraceServiceRequest()
                        request.ParseFromString(payload)
                        bridge._trace_stub.Export(request, timeout=10)
                    elif self.path == "/v1/metrics":
                        request = metrics_service_pb2.ExportMetricsServiceRequest()
                        request.ParseFromString(payload)
                        bridge._metric_stub.Export(request, timeout=10)
                    elif self.path == "/v1/logs":
                        request = logs_service_pb2.ExportLogsServiceRequest()
                        request.ParseFromString(payload)
                        bridge._logs_stub.Export(request, timeout=10)
                    else:
                        self._send_response(HTTPStatus.NOT_FOUND, b"not found")
                        return
                except DecodeError as e:
                    # Malformed OTLP payload from the instrumentation.
                    self._send_response(
                        HTTPStatus.BAD_REQUEST,
                        str(e).encode("utf-8", errors="replace"),
                    )
                    return
                except grpc.RpcError as e:
                    # Upstream collector rejected or failed the export.
                    self._send_response(
                        HTTPStatus.BAD_GATEWAY,
                        str(e).encode("utf-8", errors="replace"),
                    )
                    return

                self._send_response(HTTPStatus.OK, b"")

            def log_message(self, format: str, *args: object) -> None:
                return

            def _send_response(self, status: HTTPStatus, payload: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", self._listen_port), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

        self._channel.close()
