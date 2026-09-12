# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A windowed OTLP/gRPC capture proxy."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Condition
from types import TracebackType
from typing import Literal, NoReturn, cast
from urllib.parse import urlsplit

import grpc

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
from opentelemetry.proto.trace.v1 import trace_pb2

Signal = Literal["traces", "metrics", "logs"]

# What an SDK emits about its own processors and exporters: the names the
# semantic conventions reserve for it, and the scope prefixes the Java SDK
# reports it under. Other SDKs use the reserved names, which is what makes
# the prefix the general rule and these two the known exception.
_SELF_MONITORING_METRICS = ("otel.sdk.",)
_SELF_MONITORING_SCOPES = (
    "io.opentelemetry.sdk.",
    "io.opentelemetry.exporters.",
)
ExportRequest = (
    trace_service_pb2.ExportTraceServiceRequest
    | metrics_service_pb2.ExportMetricsServiceRequest
    | logs_service_pb2.ExportLogsServiceRequest
)
_RegisterServicer = Callable[[object, grpc.Server], None]
_register_trace = cast(
    _RegisterServicer,
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server,  # pyright: ignore[reportUnknownMemberType]
)
_register_metrics = cast(
    _RegisterServicer,
    metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server,  # pyright: ignore[reportUnknownMemberType]
)
_register_logs = cast(
    _RegisterServicer,
    logs_service_pb2_grpc.add_LogsServiceServicer_to_server,  # pyright: ignore[reportUnknownMemberType]
)


@dataclass(frozen=True)
class CaptureWindow:
    """One activation of a named scenario capture window."""

    name: str
    generation: int


@dataclass(frozen=True)
class CapturedExport:
    """A raw protobuf request and the OTLP signal that carried it."""

    signal: Signal
    request: ExportRequest
    received_unix_nano: int = 0


@dataclass(frozen=True)
class CapturedSpan:
    """The raw span fields used by scenario checks and diagnostics."""

    name: str
    kind: str
    attributes: dict[str, object]
    trace_id: bytes
    span_id: bytes
    parent_span_id: bytes
    start_time_unix_nano: int
    end_time_unix_nano: int


@dataclass(frozen=True)
class CapturedWindow:
    """Decoded scenario telemetry together with its original OTLP exports."""

    name: str
    generation: int
    exports: tuple[CapturedExport, ...]
    spans: tuple[CapturedSpan, ...]
    metric_names: tuple[str, ...]
    event_names: tuple[str, ...]


@dataclass(frozen=True)
class CaptureSnapshot:
    """An atomic view used by event-driven persistent action windows.

    ``in_flight`` counts what is still on its way upstream. A window's
    exports are recorded here before that forward starts, so this is what
    :meth:`OtlpCaptureProxy.drain` waits on, not what an action is judged
    on.
    """

    exports: tuple[CapturedExport, ...]
    in_flight: int


class UnexpectedExportsError(RuntimeError):
    """Exports reached the proxy while no capture window was active."""


class _IngressClosedError(Exception):
    """An export arrived after the proxy stopped accepting them."""


_INGRESS_CLOSED_DETAIL = (
    "the OTLP capture service is no longer accepting exports"
)


class _TraceService(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self, capture: OtlpCapture) -> None:
        self._capture = capture

    def Export(
        self,
        request: trace_service_pb2.ExportTraceServiceRequest,
        context: grpc.ServicerContext,
    ) -> trace_service_pb2.ExportTraceServiceResponse:
        return self._capture.export_trace(request, context)


class _MetricsService(metrics_service_pb2_grpc.MetricsServiceServicer):
    def __init__(self, capture: OtlpCapture) -> None:
        self._capture = capture

    def Export(
        self,
        request: metrics_service_pb2.ExportMetricsServiceRequest,
        context: grpc.ServicerContext,
    ) -> metrics_service_pb2.ExportMetricsServiceResponse:
        return self._capture.export_metrics(request, context)


class _LogsService(logs_service_pb2_grpc.LogsServiceServicer):
    def __init__(self, capture: OtlpCapture) -> None:
        self._capture = capture

    def Export(
        self,
        request: logs_service_pb2.ExportLogsServiceRequest,
        context: grpc.ServicerContext,
    ) -> logs_service_pb2.ExportLogsServiceResponse:
        return self._capture.export_logs(request, context)


class OtlpCaptureProxy:
    """Captures OTLP Export requests in windows and forwards them to Weaver.

    ``upstream_endpoint`` and ``bind_address`` are insecure gRPC endpoints.
    They may be either ``host:port`` targets or ``http://host:port`` URLs.
    """

    def __init__(
        self,
        upstream_endpoint: str,
        *,
        bind_address: str = "127.0.0.1:0",
        max_workers: int = 10,
        forward_timeout: float | None = 30.0,
    ) -> None:
        bind_target = _grpc_target(bind_address)
        upstream_target = _grpc_target(upstream_endpoint)
        self._condition = Condition()
        self._active: CaptureWindow | None = None
        self._generation = 0
        self._captured: dict[CaptureWindow, list[CapturedExport]] = {}
        self._quarantined: list[CapturedExport] = []
        self._in_flight = 0
        self._window_in_flight: Counter[CaptureWindow] = Counter()
        self._change_notifier: Callable[[], None] | None = None
        self._started = False
        self._ingress_closed = False
        self._closed = False
        self._forward_timeout = forward_timeout

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="otlp-capture"
        )
        self._server = grpc.server(self._executor)
        _register_trace(_TraceService(self), self._server)
        _register_metrics(_MetricsService(self), self._server)
        _register_logs(_LogsService(self), self._server)
        port = self._server.add_insecure_port(bind_target)
        if port == 0:
            self._executor.shutdown()
            raise RuntimeError(
                f"Could not bind OTLP capture service to {bind_target}"
            )
        host = bind_target.rsplit(":", 1)[0]
        self._target = f"{host}:{port}"

        self._channel = grpc.insecure_channel(upstream_target)
        self._trace_export = self._channel.unary_unary(
            "/opentelemetry.proto.collector.trace.v1.TraceService/Export",
            request_serializer=_serialize_trace,
            response_deserializer=(
                trace_service_pb2.ExportTraceServiceResponse.FromString
            ),
        )
        self._metrics_export = self._channel.unary_unary(
            "/opentelemetry.proto.collector.metrics.v1.MetricsService/Export",
            request_serializer=_serialize_metrics,
            response_deserializer=(
                metrics_service_pb2.ExportMetricsServiceResponse.FromString
            ),
        )
        self._logs_export = self._channel.unary_unary(
            "/opentelemetry.proto.collector.logs.v1.LogsService/Export",
            request_serializer=_serialize_logs,
            response_deserializer=(
                logs_service_pb2.ExportLogsServiceResponse.FromString
            ),
        )

    @property
    def target(self) -> str:
        """The stable ``host:port`` target shared by all three services."""

        return self._target

    @property
    def endpoint(self) -> str:
        """The stable endpoint suitable for ``OTEL_EXPORTER_OTLP_ENDPOINT``."""

        return f"http://{self._target}"

    @property
    def active_window(self) -> CaptureWindow | None:
        with self._condition:
            return self._active

    def start(self) -> OtlpCaptureProxy:
        with self._condition:
            if self._closed or self._ingress_closed:
                raise RuntimeError("OTLP capture service is closed")
            if not self._started:
                self._server.start()
                self._started = True
        return self

    def open_window(self, name: str) -> CaptureWindow:
        """Activate a new generation of ``name`` for subsequent arrivals."""

        if not name:
            raise ValueError("Capture window name must not be empty")
        with self._condition:
            if self._closed or self._ingress_closed:
                raise RuntimeError("OTLP capture service is closed")
            if self._active is not None:
                raise RuntimeError(
                    f"Capture window {self._active.name!r} is already active"
                )
            self._generation += 1
            window = CaptureWindow(name=name, generation=self._generation)
            self._captured[window] = []
            self._active = window
            return window

    def set_change_notifier(self, notifier: Callable[[], None] | None) -> None:
        """Notify an external condition when capture ingress or drain changes."""

        with self._condition:
            self._change_notifier = notifier

    def snapshot(self, window: CaptureWindow) -> CaptureSnapshot:
        """Return exports and forwarding state for ``window`` atomically."""

        with self._condition:
            if window not in self._captured:
                raise KeyError(window)
            return CaptureSnapshot(
                exports=tuple(self._captured[window]),
                in_flight=self._window_in_flight[window],
            )

    def close_window(
        self, window: CaptureWindow, *, timeout: float | None = None
    ) -> CapturedWindow:
        """Deactivate ``window``, drain its calls, and decode its telemetry."""

        with self._condition:
            if self._active != window:
                raise RuntimeError(f"Capture window {window!r} is not active")
            self._active = None
            self._wait_for(
                lambda: self._window_in_flight[window] == 0,
                timeout,
                f"capture window {window.name!r}",
            )
            return decode_window(window, tuple(self._captured[window]))

    def requests(self, window: CaptureWindow) -> tuple[CapturedExport, ...]:
        """Return an immutable snapshot of requests assigned to ``window``."""

        with self._condition:
            if window not in self._captured:
                raise KeyError(window)
            return tuple(self._captured[window])

    @property
    def quarantined_requests(self) -> tuple[CapturedExport, ...]:
        with self._condition:
            return tuple(self._quarantined)

    def raise_for_quarantined(self) -> None:
        """Report requests that arrived outside an explicit window."""

        with self._condition:
            counts = Counter(item.signal for item in self._quarantined)
        if counts:
            summary = ", ".join(
                f"{signal}={counts[signal]}"
                for signal in ("traces", "metrics", "logs")
                if counts[signal]
            )
            raise UnexpectedExportsError(
                f"OTLP exports arrived without an active capture window: {summary}"
            )

    def drain(self, *, timeout: float | None = None) -> None:
        """Wait until every forwarding call already in progress completes."""

        with self._condition:
            self._wait_for(
                lambda: self._in_flight == 0,
                timeout,
                "OTLP capture service",
            )

    def close_ingress(self, *, timeout: float | None = None) -> None:
        """Stop accepting exports, then wait for admitted ones to finish.

        Draining alone settles only what has already been recorded, and a
        call the transport had accepted but not yet handed to a servicer is
        neither recorded nor in flight. Refusing new calls first is what makes
        the captured and quarantined records final, so nothing can arrive
        behind a caller that has read them.

        The proxy stays readable afterwards; :meth:`close` releases the rest.
        """

        with self._condition:
            already_closed = self._ingress_closed
            self._ingress_closed = True
            started = self._started
        if started and not already_closed:
            # gRPC refuses new calls from the moment it is asked to stop, and
            # sets the event once every call it had admitted has finished.
            self._server.stop(30.0 if timeout is None else timeout).wait()
        self.drain(timeout=timeout)

    def _wait_for(
        self,
        predicate: Callable[[], bool],
        timeout: float | None,
        description: str,
    ) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while not predicate():
            remaining = (
                None if deadline is None else deadline - time.monotonic()
            )
            if remaining is not None and remaining <= 0:
                raise TimeoutError(f"Timed out draining {description}")
            self._condition.wait(remaining)

    def _capture(
        self, signal: Signal, request: ExportRequest
    ) -> CaptureWindow | None:
        if isinstance(request, trace_service_pb2.ExportTraceServiceRequest):
            copied: ExportRequest = (
                trace_service_pb2.ExportTraceServiceRequest()
            )
            copied.CopyFrom(request)
        elif isinstance(
            request, metrics_service_pb2.ExportMetricsServiceRequest
        ):
            copied = metrics_service_pb2.ExportMetricsServiceRequest()
            copied.CopyFrom(request)
        else:
            copied = logs_service_pb2.ExportLogsServiceRequest()
            copied.CopyFrom(request)
        item = CapturedExport(
            signal=signal,
            request=copied,
            received_unix_nano=time.time_ns(),
        )
        with self._condition:
            if self._ingress_closed:
                raise _IngressClosedError
            window = self._active
            if window is None:
                self._quarantined.append(item)
            else:
                self._captured[window].append(item)
                self._window_in_flight[window] += 1
            self._in_flight += 1
            self._condition.notify_all()
            notifier = self._change_notifier
        if notifier is not None:
            notifier()
        return window

    def _forwarded(self, window: CaptureWindow | None) -> None:
        with self._condition:
            self._in_flight -= 1
            if window is not None:
                self._window_in_flight[window] -= 1
            self._condition.notify_all()
            notifier = self._change_notifier
        if notifier is not None:
            notifier()

    def export_trace(
        self,
        request: trace_service_pb2.ExportTraceServiceRequest,
        context: grpc.ServicerContext,
    ) -> trace_service_pb2.ExportTraceServiceResponse:
        try:
            window = self._capture("traces", request)
        except _IngressClosedError:
            _abort_ingress_closed(context)
        try:
            try:
                response, call = self._trace_export.with_call(
                    request, timeout=self._forward_timeout
                )
            except grpc.RpcError as error:
                _abort_from_upstream(context, error)
            _copy_call_status(call, context)
            return response
        finally:
            self._forwarded(window)

    def export_metrics(
        self,
        request: metrics_service_pb2.ExportMetricsServiceRequest,
        context: grpc.ServicerContext,
    ) -> metrics_service_pb2.ExportMetricsServiceResponse:
        try:
            window = self._capture("metrics", request)
        except _IngressClosedError:
            _abort_ingress_closed(context)
        try:
            try:
                response, call = self._metrics_export.with_call(
                    request, timeout=self._forward_timeout
                )
            except grpc.RpcError as error:
                _abort_from_upstream(context, error)
            _copy_call_status(call, context)
            return response
        finally:
            self._forwarded(window)

    def export_logs(
        self,
        request: logs_service_pb2.ExportLogsServiceRequest,
        context: grpc.ServicerContext,
    ) -> logs_service_pb2.ExportLogsServiceResponse:
        try:
            window = self._capture("logs", request)
        except _IngressClosedError:
            _abort_ingress_closed(context)
        try:
            try:
                response, call = self._logs_export.with_call(
                    request, timeout=self._forward_timeout
                )
            except grpc.RpcError as error:
                _abort_from_upstream(context, error)
            _copy_call_status(call, context)
            return response
        finally:
            self._forwarded(window)

    def close(self, *, grace: float = 30.0) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._active = None
            already_closed = self._ingress_closed
            self._ingress_closed = True
            started = self._started
        if started and not already_closed:
            self._server.stop(grace).wait()
        self._channel.close()
        self._executor.shutdown()

    def __enter__(self) -> OtlpCaptureProxy:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


OtlpCapture = OtlpCaptureProxy


def _grpc_target(endpoint: str) -> str:
    if "://" not in endpoint:
        return endpoint
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or not parsed.netloc
        or parsed.path not in ("", "/")
    ):
        raise ValueError(
            f"Expected an insecure OTLP/gRPC endpoint, got {endpoint!r}"
        )
    return parsed.netloc


def _copy_call_status(call: grpc.Call, context: grpc.ServicerContext) -> None:
    initial = call.initial_metadata()
    if initial:
        context.send_initial_metadata(initial)
    trailing = call.trailing_metadata()
    if trailing:
        context.set_trailing_metadata(trailing)
    code = call.code()
    context.set_code(code)
    details = call.details()
    if details:
        context.set_details(details)


def _abort_ingress_closed(context: grpc.ServicerContext) -> NoReturn:
    context.abort(grpc.StatusCode.UNAVAILABLE, _INGRESS_CLOSED_DETAIL)
    raise AssertionError("grpc.ServicerContext.abort returned")


def _abort_from_upstream(
    context: grpc.ServicerContext, error: grpc.RpcError
) -> NoReturn:
    call = cast(grpc.Call, error)
    initial = call.initial_metadata()
    if initial:
        context.send_initial_metadata(initial)
    trailing = call.trailing_metadata()
    if trailing:
        context.set_trailing_metadata(trailing)
    code = call.code()
    context.abort(code, call.details() or "")
    raise AssertionError("grpc.ServicerContext.abort returned")


def _serialize_trace(
    request: trace_service_pb2.ExportTraceServiceRequest,
) -> bytes:
    return request.SerializeToString()


def _serialize_metrics(
    request: metrics_service_pb2.ExportMetricsServiceRequest,
) -> bytes:
    return request.SerializeToString()


def _serialize_logs(
    request: logs_service_pb2.ExportLogsServiceRequest,
) -> bytes:
    return request.SerializeToString()


def self_monitoring(scope_name: str, metric_name: str) -> bool:
    """Whether a metric describes the delivery pipeline rather than a library.

    An SDK reports its own queue depth and export counts, and it does so on
    every collection for as long as the process runs. That describes the
    exporter the runner configured, so a scenario is neither credited nor
    charged for it. The raw export is still kept, so the report shows it.
    """
    return metric_name.startswith(
        _SELF_MONITORING_METRICS
    ) or scope_name.startswith(_SELF_MONITORING_SCOPES)


def decode_window(
    window: CaptureWindow, exports: tuple[CapturedExport, ...]
) -> CapturedWindow:
    spans: list[CapturedSpan] = []
    metric_names: list[str] = []
    event_names: list[str] = []
    for item in exports:
        request = item.request
        if isinstance(request, trace_service_pb2.ExportTraceServiceRequest):
            for resource_spans in request.resource_spans:
                for scope_spans in resource_spans.scope_spans:
                    spans.extend(
                        _decode_span(span) for span in scope_spans.spans
                    )
        elif isinstance(
            request, metrics_service_pb2.ExportMetricsServiceRequest
        ):
            for resource_metrics in request.resource_metrics:
                for scope_metrics in resource_metrics.scope_metrics:
                    metric_names.extend(
                        metric.name
                        for metric in scope_metrics.metrics
                        if not self_monitoring(
                            scope_metrics.scope.name, metric.name
                        )
                    )
        else:
            for resource_logs in request.resource_logs:
                for scope_logs in resource_logs.scope_logs:
                    event_names.extend(
                        record.event_name
                        for record in scope_logs.log_records
                        if record.event_name
                    )
    return CapturedWindow(
        name=window.name,
        generation=window.generation,
        exports=exports,
        spans=tuple(spans),
        metric_names=tuple(metric_names),
        event_names=tuple(event_names),
    )


def _decode_span(span: trace_pb2.Span) -> CapturedSpan:
    try:
        kind = trace_pb2.Span.SpanKind.Name(span.kind)
    except ValueError:
        kind = str(span.kind)
    return CapturedSpan(
        name=span.name,
        kind=kind,
        attributes={
            attribute.key: _decode_any_value(attribute.value)
            for attribute in span.attributes
        },
        trace_id=bytes(span.trace_id),
        span_id=bytes(span.span_id),
        parent_span_id=bytes(span.parent_span_id),
        start_time_unix_nano=span.start_time_unix_nano,
        end_time_unix_nano=span.end_time_unix_nano,
    )


def _decode_any_value(value: common_pb2.AnyValue) -> object:
    field = value.WhichOneof("value")
    if field == "string_value":
        return value.string_value
    if field == "bool_value":
        return value.bool_value
    if field == "int_value":
        return value.int_value
    if field == "double_value":
        return value.double_value
    if field == "bytes_value":
        return bytes(value.bytes_value)
    if field == "array_value":
        return [_decode_any_value(item) for item in value.array_value.values]
    if field == "kvlist_value":
        return {
            item.key: _decode_any_value(item.value)
            for item in value.kvlist_value.values
        }
    return None
