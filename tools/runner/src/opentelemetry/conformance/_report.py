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
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, cast

# A span's name, kind and attributes → the registry span types it belongs to.
ClassifySpan = Callable[[str, str, Mapping[str, object]], "set[str]"]

_Json = Mapping[str, object]
Carried = dict[str, "set[str]"]


@dataclass
class Observed:
    """Every signal a run produced, keyed by span type, metric or event name."""

    spans: Carried = field(default_factory=dict[str, "set[str]"])
    metrics: Carried = field(default_factory=dict[str, "set[str]"])
    events: Carried = field(default_factory=dict[str, "set[str]"])


def read(report_dir: Path, classify: ClassifySpan) -> Observed:
    """Read every weaver report under ``report_dir`` into one :class:`Observed`."""
    observed = Observed()
    counted: dict[str, set[str]] = {}

    for path in sorted(report_dir.glob("**/*.json")):
        report = cast("object", json.loads(path.read_text(encoding="utf-8")))
        if not isinstance(report, dict):
            continue
        document = cast(_Json, report)
        _merge_counted(counted, _mapping(document.get("statistics")))
        for sample in _list(document.get("samples")):
            _read_sample(observed, sample, classify)

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
    observed: Observed, sample: object, classify: ClassifySpan
) -> None:
    if not isinstance(sample, dict):
        return
    entry = cast(_Json, sample)

    span = _mapping(entry.get("span"))
    if span:
        attributes = carried_attributes(span)
        names = set(attributes)
        for span_type in classify(
            str(span.get("name", "")), str(span.get("kind", "")), attributes
        ):
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
