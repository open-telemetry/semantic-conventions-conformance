# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Persistence and reduction of normalized runner captures."""

from __future__ import annotations

import json
from pathlib import Path

from opentelemetry.conformance._otlp_capture import (
    CapturedExport,
    CapturedWindow,
)
from opentelemetry.conformance._report import (
    read,
    scenario_report_path,
    write_capture,
    write_unwindowed,
    write_weaver,
)
from opentelemetry.conformance._semconv import _reduce
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.proto.trace.v1 import trace_pb2


def _attribute(name: str, value: str) -> common_pb2.KeyValue:
    return common_pb2.KeyValue(
        key=name, value=common_pb2.AnyValue(string_value=value)
    )


def _window(
    name: str, *exports: CapturedExport, generation: int = 1
) -> CapturedWindow:
    return CapturedWindow(
        name=name,
        generation=generation,
        exports=exports,
        spans=(),
        metric_names=(),
        event_names=(),
    )


def test_capture_report_preserves_otlp_diagnostic_fields(
    tmp_path: Path,
) -> None:
    resource = resource_pb2.Resource(
        attributes=[_attribute("service.name", "checkout")]
    )
    scope = common_pb2.InstrumentationScope(
        name="instrumentation",
        version="1.2.3",
        attributes=[_attribute("scope.attr", "x")],
    )
    traces = trace_service_pb2.ExportTraceServiceRequest(
        resource_spans=[
            trace_pb2.ResourceSpans(
                resource=resource,
                schema_url="https://resource.schema",
                scope_spans=[
                    trace_pb2.ScopeSpans(
                        scope=scope,
                        schema_url="https://scope.schema",
                        spans=[
                            trace_pb2.Span(
                                trace_id=b"\x01" * 16,
                                span_id=b"\x02" * 8,
                                parent_span_id=b"\x03" * 8,
                                name="GET /cart",
                                kind=trace_pb2.Span.SPAN_KIND_CLIENT,
                                start_time_unix_nano=101,
                                end_time_unix_nano=202,
                                attributes=[
                                    _attribute("http.request.method", "GET")
                                ],
                                events=[
                                    trace_pb2.Span.Event(
                                        time_unix_nano=150,
                                        name="exception",
                                        attributes=[
                                            _attribute(
                                                "exception.type", "Error"
                                            )
                                        ],
                                    )
                                ],
                                links=[
                                    trace_pb2.Span.Link(
                                        trace_id=b"\x04" * 16,
                                        span_id=b"\x05" * 8,
                                        attributes=[
                                            _attribute("link.attr", "x")
                                        ],
                                    )
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
                                    is_monotonic=True,
                                    data_points=[
                                        metrics_pb2.NumberDataPoint(
                                            start_time_unix_nano=203,
                                            time_unix_nano=204,
                                            as_int=5,
                                            attributes=[
                                                _attribute("route", "/cart")
                                            ],
                                        )
                                    ],
                                ),
                            )
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
                                time_unix_nano=301,
                                observed_time_unix_nano=302,
                                trace_id=b"\x01" * 16,
                                span_id=b"\x02" * 8,
                                event_name="cart.checked",
                                body=common_pb2.AnyValue(string_value="done"),
                                attributes=[_attribute("cart.id", "123")],
                            )
                        ],
                    )
                ],
            )
        ]
    )
    window = _window(
        "checkout",
        CapturedExport("traces", traces),
        CapturedExport("metrics", metrics),
        CapturedExport("logs", logs),
    )

    write_capture(tmp_path, window)
    document = json.loads(
        scenario_report_path(tmp_path, "checkout").read_text()
    )

    resource_spans = document["traces"][0]["resource_spans"][0]
    assert resource_spans["resource"]["attributes"][0]["key"] == "service.name"
    scope_spans = resource_spans["scope_spans"][0]
    assert scope_spans["scope"]["name"] == "instrumentation"
    span = scope_spans["spans"][0]
    assert span["trace_id"] and span["span_id"] and span["parent_span_id"]
    assert span["start_time_unix_nano"] == "101"
    assert span["events"][0]["time_unix_nano"] == "150"
    assert span["links"][0]["attributes"][0]["key"] == "link.attr"

    metric = document["metrics"][0]["resource_metrics"][0]["scope_metrics"][0][
        "metrics"
    ][0]
    assert metric["sum"]["aggregation_temporality"] == (
        "AGGREGATION_TEMPORALITY_DELTA"
    )
    assert metric["sum"]["data_points"][0]["attributes"][0]["key"] == "route"

    record = document["logs"][0]["resource_logs"][0]["scope_logs"][0][
        "log_records"
    ][0]
    assert record["event_name"] == "cart.checked"
    assert record["trace_id"] and record["span_id"]
    assert record["time_unix_nano"] == "301"


def test_multiple_delta_exports_union_metric_point_attributes(
    tmp_path: Path,
) -> None:
    exports: list[CapturedExport] = []
    for attribute in ("route", "error.type"):
        request = metrics_service_pb2.ExportMetricsServiceRequest(
            resource_metrics=[
                metrics_pb2.ResourceMetrics(
                    scope_metrics=[
                        metrics_pb2.ScopeMetrics(
                            metrics=[
                                metrics_pb2.Metric(
                                    name="requests",
                                    sum=metrics_pb2.Sum(
                                        aggregation_temporality=(
                                            metrics_pb2.AGGREGATION_TEMPORALITY_DELTA
                                        ),
                                        data_points=[
                                            metrics_pb2.NumberDataPoint(
                                                as_int=1,
                                                attributes=[
                                                    _attribute(attribute, "x")
                                                ],
                                            )
                                        ],
                                    ),
                                )
                            ]
                        )
                    ]
                )
            ]
        )
        exports.append(CapturedExport("metrics", request))
    write_capture(tmp_path, _window("checkout", *exports))

    observed = read(tmp_path, lambda _name, _kind, _attributes: set())

    assert observed.metrics == {"requests": {"route", "error.type"}}
    assert _reduce(
        observed,
        {
            "metrics": {
                "requests": {
                    "attributes": {
                        "route": "recommended",
                        "error.type": "recommended",
                    }
                }
            }
        },
    )["metrics"] == {"requests": ["error.type", "route"]}


def test_unwindowed_capture_contributes_to_aggregate_coverage_only(
    tmp_path: Path,
) -> None:
    request = logs_service_pb2.ExportLogsServiceRequest(
        resource_logs=[
            logs_pb2.ResourceLogs(
                scope_logs=[
                    logs_pb2.ScopeLogs(
                        log_records=[
                            logs_pb2.LogRecord(event_name="bootstrap.ready")
                        ]
                    )
                ]
            )
        ]
    )
    write_capture(tmp_path, _window("checkout"))
    write_unwindowed(
        tmp_path,
        _window(
            "unwindowed",
            CapturedExport("logs", request),
            generation=0,
        ),
    )
    write_weaver(
        tmp_path,
        {
            "live_check_result": {
                "all_advice": [
                    {
                        "id": "bad",
                        "level": "violation",
                        "message": "bad bootstrap event",
                        "context": None,
                    }
                ]
            }
        },
    )

    observed = read(tmp_path, lambda _name, _kind, _attributes: set())

    assert observed.events == {"bootstrap.ready": set()}
    assert [finding.id for finding in observed.findings] == ["bad"]
