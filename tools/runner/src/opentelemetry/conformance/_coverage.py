# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Captured telemetry from a run, reduced to one file.

The default reduction, and the reason a repo needs no code of its own to get
a coverage artifact: for every span expectation a scenario declares, the
attributes its spans actually carried, plus the metrics and events the run
produced, plus the violations Weaver found in the aggregate report. A caller
wanting a different shape passes its own reduction.

A run *always* reduces to what it saw, however badly it went. Coverage is an
observation, and an implementation that violates the conventions everywhere is
exactly the one worth having a record of. So a span no expectation selected —
including every span, when a scenario declares none — is still counted, keyed
by its kind.
"""

from __future__ import annotations

from pathlib import Path

from ._checks import ObservedSpan, selects
from ._report import (
    capture_documents,
    carried_attributes,
    finding_list,
    iter_logs,
    iter_metrics,
    iter_spans,
    read_findings,
)
from ._spec import PackageSpec, SpanMatch


def coverage(report_dir: Path, spec: PackageSpec) -> dict[str, object]:
    """Reduce captured OTLP and aggregate Weaver findings into coverage."""
    matches: dict[str, SpanMatch] = {}
    attributes: dict[str, set[str]] = {}
    metrics: set[str] = set()
    events: set[str] = set()

    def bucket(match: SpanMatch) -> set[str]:
        key = match.key()
        matches.setdefault(key, match)
        return attributes.setdefault(key, set())

    for scenario, document in capture_documents(report_dir, spec):
        metrics.update(
            str(metric["name"])
            for metric in iter_metrics(document)
            if metric.get("name")
        )
        events.update(
            str(record["event_name"])
            for record in iter_logs(document)
            if record.get("event_name")
        )
        spans = [
            ObservedSpan(
                name=str(span.get("name", "")),
                kind=str(span.get("kind", "")),
                attributes=carried_attributes(span),
            )
            for span in iter_spans(document)
        ]
        selected: set[int] = set()
        if scenario is not None:
            for expectation in scenario.spans or ():
                matched = bucket(expectation.match)
                for index, span in enumerate(spans):
                    if selects(expectation, span):
                        matched.update(span.attributes)
                        selected.add(index)

        for index, span in enumerate(spans):
            if index in selected:
                continue
            bucket(SpanMatch(attributes={}, kind=span.kind)).update(
                span.attributes
            )

    return {
        # A list of selections rather than an object: a selection is a set of
        # facets, and flattening it into a key would only make it a string to
        # unescape before reading.
        "spans": [
            {
                "match": matches[key].as_dict(),
                "attributes": sorted(attributes[key]),
            }
            for key in sorted(attributes)
        ],
        "metrics": sorted(metrics),
        "events": sorted(events),
        "findings": finding_list(read_findings(report_dir)),
    }
