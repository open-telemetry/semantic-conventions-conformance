# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Scenario expectations vs. the weaver live-check report.

Every check returns failure strings instead of raising, and none of them
short-circuit: one run reports every problem it found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Hashable, Mapping, Sequence, cast

from ._report import carried_attributes
from ._spec import (
    AttributeMatcher,
    ExpectedViolation,
    ScenarioSpec,
    SpanExpectation,
)

if TYPE_CHECKING:
    from opentelemetry.test.weaver_live_check import LiveCheckReport


@dataclass(frozen=True)
class ObservedSpan:
    name: str
    kind: str
    attributes: Mapping[str, object]


def observed_spans(report: LiveCheckReport) -> list[ObservedSpan]:
    """One entry per span sample in the report.

    Attributes weaver rejected are dropped, so an expectation cannot pass on a
    value live-check refused — the same rule the coverage reduction applies.
    """
    return [
        ObservedSpan(
            name=entry["span"].get("name", ""),
            kind=entry["span"].get("kind", ""),
            attributes=carried_attributes(
                cast("Mapping[str, object]", entry["span"])
            ),
        )
        for entry in report["samples"]
        if "span" in entry
    ]


def _seen(statistics: Mapping[str, object], *keys: str) -> set[str]:
    """The names weaver counted at least once under any of ``keys``."""
    counted: set[str] = set()
    for key in keys:
        counts = statistics.get(key)
        if not isinstance(counts, Mapping):
            continue
        counted |= {
            str(name)
            for name, count in cast("Mapping[object, object]", counts).items()
            if count
        }
    return counted


def seen_metrics(statistics: Mapping[str, object]) -> set[str]:
    """Every metric name the run produced, registry or not."""
    return _seen(
        statistics, "seen_registry_metrics", "seen_non_registry_metrics"
    )


def seen_events(statistics: Mapping[str, object]) -> set[str]:
    """Every event name the run produced, registry or not."""
    return _seen(
        statistics, "seen_registry_events", "seen_non_registry_events"
    )


@dataclass(frozen=True)
class Findings:
    """Two kinds of problem, kept apart because callers weigh them apart.

    ``failures`` mean the scenario didn't do its job. ``violations`` mean it
    did, and what it produced departs from the conventions — a result a caller
    may want to record rather than fail on.
    """

    failures: list[str]
    violations: list[str]

    def all(self) -> list[str]:
        return [*self.failures, *self.violations]


def check(spec: ScenarioSpec, report: LiveCheckReport) -> Findings:
    """Return every way the report fails to match the scenario spec."""
    statistics = report["statistics"]
    spans = observed_spans(report)
    return Findings(
        failures=[
            *(() if spec.spans is None else _check_spans(spec, spans)),
            *(
                ()
                if spec.metrics is None
                else _check_names(
                    "metric",
                    expected=set(spec.metrics),
                    seen=seen_metrics(statistics),
                )
            ),
            *(
                ()
                if spec.events is None
                else _check_names(
                    "event",
                    expected=set(spec.events),
                    seen=seen_events(statistics),
                )
            ),
        ],
        violations=_check_violations(spec, report),
    )


def selects(expectation: SpanExpectation, span: ObservedSpan) -> bool:
    match = expectation.match
    return all(
        span.attributes.get(attribute) == value
        for attribute, value in match.attributes.items()
    ) and (match.kind is None or span.kind == match.kind)


def _check_spans(
    spec: ScenarioSpec, spans: Sequence[ObservedSpan]
) -> list[str]:
    """Check each declared expectation, and that no span went undeclared."""
    failures: list[str] = []
    expectations = spec.spans or ()
    # Spans some expectation selected, so undeclared ones can be reported
    # without a second pass. Indices because a span isn't hashable.
    selected: set[int] = set()
    has_assertions = False

    for expectation in expectations:
        if expectation.count is None:
            for index, span in enumerate(spans):
                if selects(expectation, span):
                    selected.add(index)
            continue

        has_assertions = True
        matched: list[ObservedSpan] = []
        for index, span in enumerate(spans):
            if selects(expectation, span):
                matched.append(span)
                selected.add(index)
        if len(matched) != expectation.count:
            failures.append(
                f"{spec.name}: expected {expectation.count} span(s) matching "
                f"{expectation.describe()}, saw {len(matched)}"
            )
        for attribute, matcher in expectation.attributes.items():
            failure = _check_attribute(matched, attribute, matcher)
            if failure:
                failures.append(
                    f"{spec.name}: {expectation.describe()}: {failure}"
                )

    if has_assertions:
        undeclared = [
            span for index, span in enumerate(spans) if index not in selected
        ]
        if undeclared:
            failures.append(
                f"{spec.name}: {len(undeclared)} undeclared span(s): "
                f"{sorted({span.name for span in undeclared})}"
            )
    return failures


def _check_attribute(
    spans: Sequence[ObservedSpan],
    attribute: str,
    matcher: AttributeMatcher,
) -> str | None:
    present = [span for span in spans if attribute in span.attributes]
    values = [span.attributes[attribute] for span in present]

    if matcher.present is not None:
        if matcher.present and len(present) != len(spans):
            return f"{attribute} expected on every span, set on {len(present)}/{len(spans)}"
        if not matcher.present and present:
            return f"{attribute} expected on no span, set on {len(present)}/{len(spans)}"
        return None

    if matcher.distinct is not None:
        distinct = {_hashable(value) for value in values}
        if len(distinct) != matcher.distinct:
            return (
                f"{attribute} expected {matcher.distinct} distinct values, "
                f"saw {len(distinct)}: {sorted(map(repr, distinct))}"
            )
        return None

    mismatched = [value for value in values if value != matcher.equals]
    if mismatched or len(present) != len(spans):
        return (
            f"{attribute} expected {matcher.equals!r} on every span, saw "
            f"{[span.attributes.get(attribute) for span in spans]}"
        )
    return None


def _hashable(value: object) -> object:
    """Attribute values may be lists; key those by their repr so they set."""
    return value if isinstance(value, Hashable) else repr(value)


def _check_names(
    kind: str, *, expected: set[str], seen: set[str]
) -> list[str]:
    """A declared list is exact: nothing missing and nothing extra."""
    failures: list[str] = []
    if missing := expected - seen:
        failures.append(
            f"expected {kind}s {sorted(missing)} but they were not emitted"
        )
    if extra := seen - expected:
        failures.append(f"undeclared {kind}s emitted: {sorted(extra)}")
    return failures


def _matches(
    violation: Mapping[str, object], expected: ExpectedViolation
) -> bool:
    if violation.get("id") != expected.id:
        return False
    if expected.context is None:  # declared without one: any context matches
        return True
    return (violation.get("context") or {}) == dict(expected.context)


def _check_violations(
    spec: ScenarioSpec, report: LiveCheckReport
) -> list[str]:
    violations = report.violations
    expected = spec.expected_violations
    accepted = expected + spec.inherited_violations

    failures = sorted(
        _describe(violation)
        for violation in violations
        if not any(_matches(violation, e) for e in accepted)
    )
    # Only the scenario's own must still be reported; inherited ones only
    # suppress, since not every scenario reaches a package-wide gap.
    failures += sorted(
        f"{e.describe()} is no longer reported, remove it ({e.reason})"
        for e in expected
        if not any(_matches(violation, e) for violation in violations)
    )
    return failures


def _describe(violation: Mapping[str, object]) -> str:
    """One line: the advice id, and what weaver said about it.

    Not the context — weaver's message already spells out what is in it.
    """
    message = str(violation.get("message") or "").strip().rstrip(".")
    return f"[{violation.get('id')}] {message}".rstrip()
