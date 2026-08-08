# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""What a run observed, reduced to one file.

The default reduction, and the reason a repo needs no code of its own to get
a coverage artifact: for every span expectation a scenario declares, the
attributes its spans actually carried, plus the metrics and events the run
produced. A caller wanting a different shape passes its own reduction.

A run *always* reduces to what it saw, however badly it went. Coverage is an
observation, and an implementation that violates the conventions everywhere is
exactly the one worth having a record of. So a span no expectation selected —
including every span, when a scenario declares none — is still counted, keyed
by its kind.
"""

from __future__ import annotations

import json
from pathlib import Path

from ._checks import observed_spans, seen_events, seen_metrics, selects
from ._spec import PackageSpec, SpanMatch


def coverage(report_dir: Path, spec: PackageSpec) -> dict[str, object]:
    """Reduce a run's weaver reports into observed coverage."""
    matches: dict[str, SpanMatch] = {}
    attributes: dict[str, set[str]] = {}
    metrics: set[str] = set()
    events: set[str] = set()

    def bucket(match: SpanMatch) -> set[str]:
        key = match.key()
        matches.setdefault(key, match)
        return attributes.setdefault(key, set())

    for name, scenario in spec.scenarios.items():
        report_file = report_dir / f"{name}.json"
        if not report_file.is_file():
            continue
        report = json.loads(report_file.read_text())
        statistics = report.get("statistics", {})
        metrics |= seen_metrics(statistics)
        events |= seen_events(statistics)

        spans = observed_spans(report)
        selected: set[int] = set()
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
    }
