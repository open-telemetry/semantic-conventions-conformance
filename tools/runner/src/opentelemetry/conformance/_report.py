# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Persist and read captured OTLP telemetry and the aggregate Weaver report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Iterator, Mapping, cast

from google.protobuf.json_format import MessageToDict

from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2

from ._otlp_capture import CapturedWindow, self_monitoring
from ._spans import span_kind

if TYPE_CHECKING:
    from ._spec import PackageSpec, ScenarioSpec

CAPTURE_FORMAT = "opentelemetry-conformance-capture/v1"
SCENARIO_REPORT_DIR = Path("scenarios")
READINESS_REPORT = Path("readiness.json")
UNWINDOWED_REPORT = Path("unwindowed.json")
WEAVER_REPORT = Path("weaver.json")

ClassifySpan = Callable[[str, str, Mapping[str, object]], "set[str]"]
_Json = Mapping[str, object]
Carried = dict[str, "set[str]"]

_RECORDED_LEVEL = "violation"


@dataclass(frozen=True)
class Finding:
    """One Weaver violation about one signal."""

    id: str
    message: str
    context: str
    signal_type: str = ""
    signal_name: str = ""

    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.signal_type,
            self.signal_name,
            self.message,
            self.id,
            self.context,
        )

    def as_dict(self) -> dict[str, object]:
        recorded: dict[str, object] = {"id": self.id, "message": self.message}
        if self.signal_type:
            recorded["signal_type"] = self.signal_type
        if self.signal_name:
            recorded["signal_name"] = self.signal_name
        context = cast("object", json.loads(self.context))
        if context is not None:
            recorded["context"] = context
        return recorded


@dataclass
class Observed:
    """Every captured signal, reduced to the attribute names it carried."""

    spans: Carried = field(default_factory=dict[str, "set[str]"])
    metrics: Carried = field(default_factory=dict[str, "set[str]"])
    events: Carried = field(default_factory=dict[str, "set[str]"])
    findings: "set[Finding]" = field(default_factory=set["Finding"])
    resources: set[str] = field(default_factory=set[str])


def scenario_report_path(report_dir: Path, name: str) -> Path:
    return report_dir / SCENARIO_REPORT_DIR / f"{name}.json"


def capture_document(window: CapturedWindow) -> dict[str, object]:
    """Convert a capture window to stable OTLP JSON without losing hierarchy."""

    traces: list[dict[str, object]] = []
    metrics: list[dict[str, object]] = []
    logs: list[dict[str, object]] = []
    for captured in window.exports:
        request = captured.request
        document = cast(
            "dict[str, object]",
            MessageToDict(
                request,
                always_print_fields_with_no_presence=True,
                preserving_proto_field_name=True,
            ),
        )
        if isinstance(request, trace_service_pb2.ExportTraceServiceRequest):
            traces.append(document)
        elif isinstance(
            request, metrics_service_pb2.ExportMetricsServiceRequest
        ):
            metrics.append(document)
        else:
            logs.append(document)
    return {
        "format": CAPTURE_FORMAT,
        "name": window.name,
        "generation": window.generation,
        "traces": traces,
        "metrics": metrics,
        "logs": logs,
    }


def write_capture(report_dir: Path, window: CapturedWindow) -> Path:
    """Replace one scenario's normalized capture report."""

    path = scenario_report_path(report_dir, window.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, capture_document(window))
    return path


def write_readiness(report_dir: Path, window: CapturedWindow) -> Path:
    """Replace the report for what a persistent batch emitted before its first action.

    A package runs one persistent batch per shared run command; the file
    holds the most recent one.
    """

    path = report_dir / READINESS_REPORT
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(path, capture_document(window))
    return path


def write_unwindowed(report_dir: Path, window: CapturedWindow) -> Path:
    """Replace the report for exports captured outside scenario windows."""

    path = report_dir / UNWINDOWED_REPORT
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(path, capture_document(window))
    return path


def write_weaver(report_dir: Path, report: object) -> Path:
    """Replace the one aggregate Weaver report for this run."""

    path = report_dir / WEAVER_REPORT
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(path, report)
    return path


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_capture(path: Path) -> _Json:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} is not a {CAPTURE_FORMAT} report")
    capture = cast(_Json, document)
    if capture.get("format") != CAPTURE_FORMAT:
        raise ValueError(f"{path} is not a {CAPTURE_FORMAT} report")
    return capture


def capture_documents(
    report_dir: Path, spec: PackageSpec | None = None
) -> Iterator[tuple[ScenarioSpec | None, _Json]]:
    """Yield current scenario captures, then any unwindowed capture."""

    if spec is None:
        scenario_paths = sorted(
            (report_dir / SCENARIO_REPORT_DIR).glob("*.json")
        )
        for path in scenario_paths:
            yield None, load_capture(path)
    else:
        for name, scenario in spec.scenarios.items():
            path = scenario_report_path(report_dir, name)
            if path.is_file():
                yield scenario, load_capture(path)

    unwindowed = report_dir / UNWINDOWED_REPORT
    if unwindowed.is_file():
        yield None, load_capture(unwindowed)


def collect_findings(document: object) -> set[Finding]:
    """Return every violation in a Weaver report."""

    found: set[Finding] = set()
    if isinstance(document, dict):
        owner = cast(_Json, document)
        result = _mapping(owner.get("live_check_result"))
        for entry in _list(result.get("all_advice")):
            advice = _mapping(entry)
            if advice.get("level") != _RECORDED_LEVEL:
                continue
            found.add(
                Finding(
                    id=str(advice.get("id") or ""),
                    message=str(advice.get("message") or ""),
                    context=json.dumps(
                        cast("object", advice.get("context")), sort_keys=True
                    ),
                    signal_type=str(advice.get("signal_type") or ""),
                    signal_name=str(advice.get("signal_name") or ""),
                )
            )
        for value in owner.values():
            found |= collect_findings(value)
    elif isinstance(document, list):
        for item in cast("list[object]", document):
            found |= collect_findings(item)
    return found


def read_findings(report_dir: Path) -> set[Finding]:
    path = report_dir / WEAVER_REPORT
    if not path.is_file():
        return set()
    return collect_findings(json.loads(path.read_text(encoding="utf-8")))


def finding_list(findings: Iterable[Finding]) -> list[dict[str, object]]:
    return [
        finding.as_dict() for finding in sorted(findings, key=Finding.sort_key)
    ]


def iter_spans(document: _Json) -> Iterator[_Json]:
    for request in _list(document.get("traces")):
        for resource_spans in _list(_mapping(request).get("resource_spans")):
            for scope_spans in _list(
                _mapping(resource_spans).get("scope_spans")
            ):
                for span in _list(_mapping(scope_spans).get("spans")):
                    yield _mapping(span)


def iter_metrics(document: _Json) -> Iterator[tuple[str, _Json]]:
    """Every metric with the scope that reported it.

    The scope is what tells an SDK's report on its own exporter apart from a
    measurement of the library under test, so it travels with the metric.
    """

    for request in _list(document.get("metrics")):
        for resource_metrics in _list(
            _mapping(request).get("resource_metrics")
        ):
            for scope_metrics in _list(
                _mapping(resource_metrics).get("scope_metrics")
            ):
                scope = _mapping(_mapping(scope_metrics).get("scope"))
                name = scope.get("name")
                scope_name = name if isinstance(name, str) else ""
                for metric in _list(_mapping(scope_metrics).get("metrics")):
                    yield scope_name, _mapping(metric)


def iter_logs(document: _Json) -> Iterator[_Json]:
    for request in _list(document.get("logs")):
        for resource_logs in _list(_mapping(request).get("resource_logs")):
            for scope_logs in _list(_mapping(resource_logs).get("scope_logs")):
                for record in _list(_mapping(scope_logs).get("log_records")):
                    yield _mapping(record)


def resource_attributes(document: _Json) -> Iterator[Mapping[str, object]]:
    for signal, resource_key in (
        ("traces", "resource_spans"),
        ("metrics", "resource_metrics"),
        ("logs", "resource_logs"),
    ):
        for request in _list(document.get(signal)):
            for resource_group in _list(_mapping(request).get(resource_key)):
                resource = _mapping(_mapping(resource_group).get("resource"))
                yield carried_attributes(resource)


def metric_point_attributes(metric: _Json) -> set[str]:
    """Return the union of attributes on every point in one metric export."""

    for data_type in (
        "gauge",
        "sum",
        "histogram",
        "exponential_histogram",
        "summary",
    ):
        data = _mapping(metric.get(data_type))
        if data:
            return {
                name
                for point in _list(data.get("data_points"))
                for name in carried_attributes(_mapping(point))
            }
    return set()


def carried_attributes(owner: _Json) -> dict[str, object]:
    """Decode OTLP JSON attributes into a mapping."""

    attributes: dict[str, object] = {}
    for record in _list(owner.get("attributes")):
        attribute = _mapping(record)
        key = attribute.get("key")
        if isinstance(key, str) and key:
            attributes[key] = _any_value(_mapping(attribute.get("value")))
    return attributes


def _any_value(value: _Json) -> object:
    if "int_value" in value:
        try:
            return int(str(value["int_value"]))
        except ValueError:
            return value["int_value"]
    for key in (
        "string_value",
        "bool_value",
        "double_value",
        "bytes_value",
    ):
        if key in value:
            return value[key]
    array = _mapping(value.get("array_value"))
    if array:
        return [
            _any_value(_mapping(item)) for item in _list(array.get("values"))
        ]
    items = _mapping(value.get("kvlist_value"))
    if items:
        return {
            str(item.get("key")): _any_value(_mapping(item.get("value")))
            for raw in _list(items.get("values"))
            if (item := _mapping(raw)).get("key")
        }
    return None


def read(
    report_dir: Path,
    classify: ClassifySpan,
    spec: PackageSpec | None = None,
) -> Observed:
    """Reduce captured OTLP telemetry and aggregate Weaver findings."""

    observed = Observed(findings=read_findings(report_dir))
    for scenario, document in capture_documents(report_dir, spec):
        for resource in resource_attributes(document):
            observed.resources.update(resource)

        for span in iter_spans(document):
            attributes = carried_attributes(span)
            types = _declared_types(scenario, span, attributes)
            if types is None:
                types = classify(
                    str(span.get("name", "")),
                    str(span.get("kind", "")),
                    attributes,
                )
            for span_type in types:
                observed.spans.setdefault(span_type, set()).update(attributes)

        for scope_name, metric in iter_metrics(document):
            name = metric.get("name")
            if (
                isinstance(name, str)
                and name
                and not self_monitoring(scope_name, name)
            ):
                observed.metrics.setdefault(name, set()).update(
                    metric_point_attributes(metric)
                )

        for record in iter_logs(document):
            name = record.get("event_name")
            if isinstance(name, str) and name:
                observed.events.setdefault(name, set()).update(
                    carried_attributes(record)
                )
    return observed


def _declared_types(
    scenario: ScenarioSpec | None,
    span: _Json,
    attributes: Mapping[str, object],
) -> set[str] | None:
    if scenario is None or not scenario.spans:
        return None
    kind = str(span.get("kind", ""))
    for expectation in scenario.spans:
        match = expectation.match
        if match.type is None:
            continue
        if match.kind is not None and span_kind(match.kind) != span_kind(kind):
            continue
        if all(
            attributes.get(key) == value
            for key, value in match.attributes.items()
        ):
            return {match.type}
    return None


def _mapping(value: object) -> _Json:
    return cast(_Json, value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []
