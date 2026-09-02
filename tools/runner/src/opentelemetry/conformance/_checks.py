# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Checks for scenario telemetry and aggregate package violations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Hashable, Mapping, Sequence

from ._otlp_capture import CapturedSpan, CapturedWindow
from ._spans import span_kind
from ._spec import (
    AttributeMatcher,
    ExpectedViolation,
    PackageSpec,
    ScenarioSpec,
    SpanExpectation,
)

if TYPE_CHECKING:
    from opentelemetry.test.weaver_live_check import LiveCheckReport


@dataclass(frozen=True)
class PackageFindings:
    """Unexpected findings and stale declarations from one package report."""

    failures: list[str]
    violations: list[str]


@dataclass(frozen=True)
class ObservedSpan:
    """A span read from a normalized capture for coverage reduction."""

    name: str
    kind: str
    attributes: Mapping[str, object]


def check_scenario_telemetry(
    spec: ScenarioSpec, window: CapturedWindow
) -> list[str]:
    """Evaluate one scenario contract against its raw captured OTLP window."""
    return [
        *(() if spec.spans is None else _check_spans(spec, window.spans)),
        *(
            ()
            if spec.metrics is None
            else _check_names(
                "metric",
                expected=set(spec.metrics),
                seen=set(window.metric_names) - set(spec.optional_metrics),
            )
        ),
        *(
            ()
            if spec.events is None
            else _check_names(
                "event",
                expected=set(spec.events),
                seen=set(window.event_names),
            )
        ),
    ]


def check_package_violations(
    spec: PackageSpec, report: LiveCheckReport, *, complete: bool
) -> PackageFindings:
    """Evaluate Weaver's aggregate findings once for the package."""
    violations = report.violations
    expected = spec.expected_violations
    unexpected = sorted(
        describe_violation(violation)
        for violation in violations
        if not any(_matches(violation, item) for item in expected)
    )
    stale = (
        sorted(
            f"{item.describe()} is no longer reported, remove it "
            f"({item.reason})"
            for item in expected
            if not any(_matches(violation, item) for violation in violations)
        )
        if complete
        else []
    )
    return PackageFindings(failures=stale, violations=unexpected)


def selects(
    expectation: SpanExpectation, span: CapturedSpan | ObservedSpan
) -> bool:
    match = expectation.match
    return all(
        span.attributes.get(attribute) == value
        for attribute, value in match.attributes.items()
    ) and (match.kind is None or span_kind(span.kind) == span_kind(match.kind))


def _check_spans(
    spec: ScenarioSpec, spans: Sequence[CapturedSpan]
) -> list[str]:
    """Check each declared expectation, and that no span went undeclared."""
    failures: list[str] = []
    expectations = spec.spans or ()
    selected: set[int] = set()
    has_assertions = False

    for expectation in expectations:
        if expectation.count is None:
            for index, span in enumerate(spans):
                if selects(expectation, span):
                    selected.add(index)
            continue

        has_assertions = True
        matched: list[CapturedSpan] = []
        for index, span in enumerate(spans):
            if selects(expectation, span):
                matched.append(span)
                selected.add(index)
        if len(matched) != expectation.count:
            failures.append(
                f"{spec.display_name}: expected {expectation.count} span(s) matching "
                f"{expectation.describe()}, saw {len(matched)}"
            )
        for attribute, matcher in expectation.attributes.items():
            failure = _check_attribute(matched, attribute, matcher)
            if failure:
                failures.append(
                    f"{spec.display_name}: {expectation.describe()}: {failure}"
                )

    if has_assertions:
        undeclared = [
            span for index, span in enumerate(spans) if index not in selected
        ]
        if undeclared:
            failures.append(
                f"{spec.display_name}: {len(undeclared)} undeclared span(s): "
                f"{sorted({span.name for span in undeclared})}"
            )
    return failures


def _check_attribute(
    spans: Sequence[CapturedSpan],
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
    if expected.context is None:
        return True
    return (violation.get("context") or {}) == dict(expected.context)


def describe_violation(violation: Mapping[str, object]) -> str:
    """Return the advice id and Weaver's message on one line."""
    message = str(violation.get("message") or "").strip().rstrip(".")
    return f"[{violation.get('id')}] {message}".rstrip()
