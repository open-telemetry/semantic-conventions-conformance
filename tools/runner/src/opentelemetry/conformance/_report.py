# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A run's weaver reports, read as "what each signal carried".

One :class:`Observed` over every report in a directory: per span type, per
metric and per event, the attribute names the run carried on it at least once.
An attribute missing where the registry requires it is a weaver violation, not
a coverage gap, so the union is all a reduction needs.

A span becomes a span *type* through a ``classify`` callable — the registry
declares what a type carries but not how to recognise one, so that knowledge
belongs to the conventions, not here.

Alongside what a run carried, what weaver found wrong with it: the violations
the reports hold, deduplicated. The same gap is reported once per signal it
appears on, and a coverage file records the gap, not how many times a run
tripped over it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Mapping, cast

if TYPE_CHECKING:
    from ._spec import PackageSpec, ScenarioSpec

# A span's name, kind and attributes → the registry span types it belongs to.
ClassifySpan = Callable[[str, str, Mapping[str, object]], "set[str]"]

_Json = Mapping[str, object]
Carried = dict[str, "set[str]"]


# The weaver advice level a coverage file records as a finding.
_RECORDED_LEVEL = "violation"


@dataclass(frozen=True)
class Finding:
    """One thing weaver said, independent of how often it said it.

    ``context`` is kept serialised so two findings with the same message about
    different attributes stay apart, and so a finding is hashable.
    """

    id: str
    message: str
    context: str

    def sort_key(self) -> tuple[str, str, str]:
        return (self.message, self.id, self.context)

    def as_dict(self) -> dict[str, object]:
        """The finding as a coverage file records it.

        ``context`` is left out when weaver reported none, rather than
        committed as a null.
        """
        recorded: dict[str, object] = {"id": self.id, "message": self.message}
        context = cast("object", json.loads(self.context))
        if context is not None:
            recorded["context"] = context
        return recorded


@dataclass
class Observed:
    """Every signal a run produced, keyed by span type, metric or event name."""

    spans: Carried = field(default_factory=dict[str, "set[str]"])
    metrics: Carried = field(default_factory=dict[str, "set[str]"])
    events: Carried = field(default_factory=dict[str, "set[str]"])
    findings: "set[Finding]" = field(default_factory=set["Finding"])
    resources: set[str] = field(default_factory=set[str])


def collect_findings(document: object) -> set[Finding]:
    """Every violation anywhere in a report.

    Weaver attaches advice to whatever it checked — a span, an attribute, a
    resource — so the report is walked rather than read at known keys.
    """
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
                )
            )
        for value in owner.values():
            found |= collect_findings(value)
    elif isinstance(document, list):
        for item in cast("list[object]", document):
            found |= collect_findings(item)
    return found


def finding_list(findings: Iterable[Finding]) -> list[dict[str, object]]:
    """Findings as a coverage file records them, in a stable committed order."""
    return [
        finding.as_dict()
        for finding in sorted(findings, key=Finding.sort_key)
    ]


def read(
    report_dir: Path,
    classify: ClassifySpan,
    spec: PackageSpec | None = None,
) -> Observed:
    """Read every weaver report under ``report_dir`` into one :class:`Observed`."""
    observed = Observed()
    counted: dict[str, set[str]] = {}

    for path in sorted(report_dir.glob("**/*.json")):
        report = cast("object", json.loads(path.read_text(encoding="utf-8")))
        if not isinstance(report, dict):
            continue
        document = cast(_Json, report)
        _merge_counted(counted, _mapping(document.get("statistics")))
        observed.findings |= collect_findings(document)
        scenario_spec = spec.scenarios.get(path.stem) if spec else None
        for sample in _list(document.get("samples")):
            _read_sample(observed, sample, classify, scenario_spec)

    # Weaver counts signals it kept no sample of. Record those too, carrying
    # nothing — there is nothing to read attributes off.
    for key, signals in (
        ("seen_registry_metrics", observed.metrics),
        ("seen_registry_events", observed.events),
    ):
        for name in counted.get(key, set()):
            signals.setdefault(name, set())

    return observed


_COUNT_KEYS = ("seen_registry_metrics", "seen_registry_events")


def _merge_counted(into: dict[str, set[str]], statistics: _Json) -> None:
    """Merge the signal names one report saw at least once.

    A directory holds one report per scenario, so the run saw a signal if any
    scenario did.
    """
    for key in _COUNT_KEYS:
        merged = into.setdefault(key, set())
        for name, count in _mapping(statistics.get(key)).items():
            if isinstance(count, int) and count > 0:
                merged.add(name)


def _read_sample(
    observed: Observed,
    sample: object,
    classify: ClassifySpan,
    scenario_spec: ScenarioSpec | None = None,
) -> None:
    if not isinstance(sample, dict):
        return
    entry = cast(_Json, sample)

    resource = _mapping(entry.get("resource"))
    if resource:
        observed.resources.update(carried_attributes(resource))

    span = _mapping(entry.get("span"))
    if span:
        attributes = carried_attributes(span)
        names = set(attributes)

        span_types = None
        if scenario_spec and scenario_spec.spans:
            kind = str(span.get("kind", ""))
            for expectation in scenario_spec.spans:
                match = expectation.match
                if match.type is not None:
                    if match.kind is not None:
                        m_kind = match.kind.upper().removeprefix("SPAN_KIND_")
                        s_kind = kind.upper().removeprefix("SPAN_KIND_")
                        if m_kind != s_kind:
                            continue
                    if all(attributes.get(attr) == val for attr, val in match.attributes.items()):
                        span_types = {match.type}
                        break

        if span_types is None:
            span_types = classify(
                str(span.get("name", "")), str(span.get("kind", "")), attributes
            )

        for span_type in span_types:
            observed.spans.setdefault(span_type, set()).update(names)

    metric = _mapping(entry.get("metric"))
    if metric.get("name"):
        observed.metrics.setdefault(str(metric["name"]), set()).update(
            _data_point_attributes(metric)
        )

    log = _mapping(entry.get("log"))
    if log.get("event_name"):
        observed.events.setdefault(str(log["event_name"]), set()).update(
            carried_attributes(log)
        )


def _data_point_attributes(metric: _Json) -> set[str]:
    """Every attribute name across a metric's data points.

    A metric's attributes are per data point, and a run's points differ by
    exactly the dimensions being recorded, so the union is what it carried.
    """
    return {
        name
        for point in _list(metric.get("data_points"))
        for name in carried_attributes(_mapping(point))
    }


def carried_attributes(owner: _Json) -> dict[str, object]:
    """The owner's attributes by name, dropping any weaver rejected."""
    attributes: dict[str, object] = {}
    for record in _list(owner.get("attributes")):
        attribute = _mapping(record)
        name = attribute.get("name")
        if isinstance(name, str) and name and _counts_as_present(attribute):
            attributes[name] = attribute.get("value")
    return attributes


def _counts_as_present(attribute: _Json) -> bool:
    """An attribute whose value weaver rejected didn't really arrive.

    A ``type_mismatch`` means the name is there but holding something the
    registry doesn't allow — recording it as coverage would claim conformance
    the run didn't have.
    """
    result = _mapping(attribute.get("live_check_result"))
    return not any(
        _mapping(advice).get("id") == "type_mismatch"
        for advice in _list(result.get("all_advice"))
    )


def _mapping(value: object) -> _Json:
    """A JSON object, or an empty one — reports are read defensively."""
    return cast(_Json, value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []
