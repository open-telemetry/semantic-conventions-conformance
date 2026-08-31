# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""An OTLP/HTTP receiver that forwards protobuf requests to OTLP/gRPC."""

from __future__ import annotations

import gzip
import io
import logging
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import zlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Callable, Protocol, cast
from urllib.parse import urlsplit

import grpc
from google.protobuf.message import DecodeError, Message

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.logs.v1.logs_service_pb2_grpc import (
    LogsServiceStub,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2_grpc import (
    MetricsServiceStub,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc import (
    TraceServiceStub,
)

logger = logging.getLogger(__name__)

_CONTENT_TYPE = "application/x-protobuf"
_HEALTH_PATH = "/health"
_MAX_BODY_BYTES = 64 * 1024 * 1024
_STARTUP_TIMEOUT_SECONDS = 5.0
_UPSTREAM_TIMEOUT_SECONDS = 30.0
_CONTENT_LENGTH = re.compile(r"[0-9]+")

_Forward = Callable[[bytes], bytes]


class _Export(Protocol):
    def __call__(
        self,
        request: Message,
        *,
        timeout: float,
    ) -> Message: ...


class _Stub(Protocol):
    Export: _Export


class OtlpHttpBridge:
    """Receive OTLP/HTTP protobuf and forward it to an OTLP/gRPC endpoint."""

    def __init__(self, grpc_endpoint: str) -> None:
        target = _grpc_target(grpc_endpoint)
        self._channel = grpc.insecure_channel(target)
        traces = cast("_Stub", TraceServiceStub(self._channel))
        metrics = cast("_Stub", MetricsServiceStub(self._channel))
        logs = cast("_Stub", LogsServiceStub(self._channel))
        self._routes: dict[str, _Forward] = {
            "/v1/traces": lambda body: self._export(
                body,
                ExportTraceServiceRequest,
                ExportTraceServiceResponse,
                traces.Export,
            ),
            "/v1/metrics": lambda body: self._export(
                body,
                ExportMetricsServiceRequest,
                ExportMetricsServiceResponse,
                metrics.Export,
            ),
            "/v1/logs": lambda body: self._export(
                body,
                ExportLogsServiceRequest,
                ExportLogsServiceResponse,
                logs.Export,
            ),
        }
        self._server = _BridgeServer(("127.0.0.1", 0), self)
        self._thread: threading.Thread | None = None
        self._closed = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def forwarder(self, path: str) -> _Forward | None:
        return self._routes.get(path)

    def start(self) -> OtlpHttpBridge:
        if self._closed:
            raise RuntimeError("OTLP/HTTP bridge is closed")
        if self._thread is not None:
            return self

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="otel-conformance-otlp-http",
            daemon=True,
        )
        self._thread.start()
        try:
            self._wait_for_health()
        except BaseException:
            self.close()
            raise
        return self

    def _wait_for_health(self) -> None:
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(  # noqa: S310
                    f"{self.url}{_HEALTH_PATH}", timeout=0.5
                ) as response:
                    if response.status == HTTPStatus.OK:
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            time.sleep(0.01)
        raise RuntimeError(
            f"OTLP/HTTP bridge did not become healthy on {self.url}"
        )

    def _export(
        self,
        body: bytes,
        request_type: type[Message],
        response_type: type[Message],
        export: _Export,
    ) -> bytes:
        request = request_type()
        request.ParseFromString(body)
        response = export(request, timeout=_UPSTREAM_TIMEOUT_SECONDS)
        if not isinstance(response, response_type):
            raise RuntimeError(
                f"OTLP/gRPC returned {type(response).__name__}, "
                f"expected {response_type.__name__}"
            )
        return response.SerializeToString()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join()
            self._thread = None
        self._server.server_close()
        self._channel.close()

    def __enter__(self) -> OtlpHttpBridge:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        bridge: OtlpHttpBridge,
    ) -> None:
        self.bridge = bridge
        super().__init__(address, _Handler)

    def handle_error(
        self,
        request: socket.socket | tuple[bytes, socket.socket],
        client_address: tuple[str, int],
    ) -> None:
        error = sys.exc_info()[1]
        if isinstance(
            error,
            (BrokenPipeError, ConnectionAbortedError, ConnectionResetError),
        ):
            return
        super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == _HEALTH_PATH:
            self._respond(HTTPStatus.OK, b"ok\n")
            return
        self._error(HTTPStatus.NOT_FOUND, "unknown endpoint")

    def do_POST(self) -> None:  # noqa: N802
        server = cast("_BridgeServer", self.server)
        forward = server.bridge.forwarder(self.path)
        if forward is None:
            self._error(HTTPStatus.NOT_FOUND, "unknown OTLP endpoint")
            return

        length = self._content_length()
        if length is None:
            return
        encoding = self.headers.get("Content-Encoding", "identity").lower()
        if encoding not in {"identity", "gzip"}:
            self._error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                f"unsupported content encoding: {encoding}",
            )
            return
        content_type = self.headers.get("Content-Type", "").lower()
        if content_type != _CONTENT_TYPE:
            self._error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                f"content type must be {_CONTENT_TYPE}",
            )
            return

        body = self.rfile.read(length)
        if len(body) != length:
            self._error(
                HTTPStatus.BAD_REQUEST,
                f"content length was {length}, received {len(body)} bytes",
            )
            return
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                    body = compressed.read(_MAX_BODY_BYTES + 1)
            # zlib.error, for a corrupt deflate stream under an intact gzip
            # header, derives from Exception rather than OSError.
            except (gzip.BadGzipFile, EOFError, OSError, zlib.error):
                self._error(HTTPStatus.BAD_REQUEST, "invalid gzip body")
                return
            if len(body) > _MAX_BODY_BYTES:
                self._error(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    f"decompressed body exceeds {_MAX_BODY_BYTES} bytes",
                )
                return

        try:
            response = forward(body)
        except DecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "invalid protobuf payload")
            return
        except grpc.RpcError as error:
            details = error.details() or error.code().name
            self._error(
                HTTPStatus.BAD_GATEWAY,
                f"OTLP/gRPC upstream failed: {details}",
            )
            return
        except Exception:
            logger.exception("OTLP/gRPC forwarding failed")
            self._error(
                HTTPStatus.BAD_GATEWAY,
                "OTLP/gRPC upstream failed",
            )
            return

        self._respond(HTTPStatus.OK, response, content_type=_CONTENT_TYPE)

    def _content_length(self) -> int | None:
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(
                HTTPStatus.BAD_REQUEST,
                "transfer encoding is not supported; send Content-Length",
            )
            return None
        values = self.headers.get_all("Content-Length", [])
        if not values:
            self._error(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
            return None
        if len(values) != 1 or _CONTENT_LENGTH.fullmatch(values[0]) is None:
            self._error(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
            return None
        length = int(values[0])
        if length > _MAX_BODY_BYTES:
            self._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"Content-Length exceeds {_MAX_BODY_BYTES} bytes",
            )
            return None
        return length

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._respond(
            status,
            f"{message}\n".encode(),
            content_type="text/plain; charset=utf-8",
        )

    def _respond(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def _grpc_target(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid OTLP/gRPC endpoint {endpoint!r}") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname is None
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"invalid OTLP/gRPC endpoint {endpoint!r}; "
            "expected http://host:port"
        )
    host = (
        f"[{parsed.hostname}]"
        if ":" in parsed.hostname
        else parsed.hostname
    )
    return f"{host}:{port}"
