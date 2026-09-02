# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Scenario telemetry and package Weaver finding checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from opentelemetry.conformance._checks import (
    check_package_violations,
    check_scenario_telemetry,
)
from opentelemetry.conformance._coverage import coverage
from opentelemetry.conformance._otlp_capture import (
    CapturedSpan,
    CapturedWindow,
)
from opentelemetry.conformance._report import CAPTURE_FORMAT, WEAVER_REPORT
from opentelemetry.conformance._spec import (
    AttributeMatcher,
    ExpectedViolation,
    PackageSpec,
    ScenarioSpec,
    ServerSpec,
    SpanExpectation,
    SpanMatch,
    WeaverSpec,
)


def span_sample(
    name: str = "chat gpt-4o-mini",
    kind: str = "CLIENT",
    **attributes: object,
) -> dict[str, Any]:
    return {
        "span": {
            "name": name,
            "kind": kind,
            "attributes": [
                {"name": key, "value": value}
                for key, value in attributes.items()
            ],
        }
    }


def write_capture_report(
    directory: Path,
    name: str,
    *samples: dict[str, Any],
    metrics: tuple[str, ...] = (),
    events: tuple[str, ...] = (),
) -> None:
    spans = []
    for sample in samples:
        raw = sample["span"]
        spans.append(
            {
                **{key: raw[key] for key in ("name", "kind")},
                "attributes": [
                    {
                        "key": attribute["name"],
                        "value": {"string_value": attribute["value"]},
                    }
                    for attribute in raw["attributes"]
                ],
            }
        )
    captures = directory / "scenarios"
    captures.mkdir(parents=True, exist_ok=True)
    (captures / f"{name}.json").write_text(
        json.dumps(
            {
                "format": CAPTURE_FORMAT,
                "name": name,
                "generation": 1,
                "traces": [
                    {"resource_spans": [{"scope_spans": [{"spans": spans}]}]}
                ],
                "metrics": [
                    {
                        "resource_metrics": [
                            {
                                "scope_metrics": [
                                    {
                                        "metrics": [
                                            {"name": metric}
                                            for metric in metrics
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "logs": [
                    {
                        "resource_logs": [
                            {
                                "scope_logs": [
                                    {
                                        "log_records": [
                                            {"event_name": event}
                                            for event in events
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ],
            }
        )
    )


class WeaverReport(dict[str, Any]):
    """The public violation API needed by the package check."""

    def __init__(
        self,
        violations: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.violations = violations or []


def captured_span(
    name: str = "chat gpt-4o-mini",
    kind: str = "SPAN_KIND_CLIENT",
    **attributes: object,
) -> CapturedSpan:
    return CapturedSpan(
        name=name,
        kind=kind,
        attributes=attributes,
        trace_id=b"\x01" * 16,
        span_id=b"\x02" * 8,
        parent_span_id=b"",
        start_time_unix_nano=101,
        end_time_unix_nano=202,
    )


def window(
    spans: list[CapturedSpan] | None = None,
    *,
    metrics: tuple[str, ...] = (),
    events: tuple[str, ...] = (),
) -> CapturedWindow:
    return CapturedWindow(
        name="inference",
        generation=1,
        exports=(),
        spans=tuple(spans or ()),
        metric_names=metrics,
        event_names=events,
    )


def check(spec: ScenarioSpec, captured: CapturedWindow) -> list[str]:
    return check_scenario_telemetry(spec, captured)


def package_spec(
    expected: tuple[ExpectedViolation, ...] = (),
) -> PackageSpec:
    return PackageSpec(
        instrumented_library="demo",
        instrumentation_library="demo-instrumentation",
        directory=Path("."),
        env={},
        weaver=WeaverSpec(),
        server=ServerSpec(),
        setup=None,
        scenarios={"inference": scenario()},
        expected_violations=expected,
    )


def scenario(**kwargs: Any) -> ScenarioSpec:
    defaults: dict[str, Any] = {
        "name": "inference",
        "directory": Path("."),
        "env": {},
        "run": ("python", "inference.py"),
        "spans": None,
        "metrics": None,
        "events": None,
    }
    return ScenarioSpec(**{**defaults, **kwargs})


CHAT = SpanExpectation(
    match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
    count=1,
    attributes={},
)


def test_no_expectations_passes_on_anything() -> None:
    captured = window(
        [captured_span(**{"gen_ai.operation.name": "chat"})],
        metrics=("gen_ai.client.token.usage",),
    )

    assert check(scenario(), captured) == []


def test_span_count_must_be_exact() -> None:
    captured = window(
        [
            captured_span(**{"gen_ai.operation.name": "chat"}),
            captured_span(**{"gen_ai.operation.name": "chat"}),
        ]
    )

    (failure,) = check(scenario(spans=(CHAT,)), captured)
    assert "expected 1 span(s)" in failure
    assert "saw 2" in failure


def test_undeclared_span_fails() -> None:
    captured = window(
        [
            captured_span(**{"gen_ai.operation.name": "chat"}),
            captured_span(
                name="execute_tool lookup",
                **{"gen_ai.operation.name": "execute_tool"},
            ),
        ]
    )

    (failure,) = check(scenario(spans=(CHAT,)), captured)
    assert "1 undeclared span(s)" in failure
    assert "execute_tool lookup" in failure


def test_match_on_kind() -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={}, kind="CLIENT"),
        count=1,
        attributes={},
    )

    assert (
        check(scenario(spans=(expectation,)), window([captured_span()])) == []
    )
    assert (
        check(
            scenario(spans=(expectation,)),
            window([captured_span(kind="SPAN_KIND_SERVER")]),
        )
        != []
    )


def test_a_kind_matches_however_it_is_spelled() -> None:
    """Weaver writes ``client``; a spec writes the ``CLIENT`` of the API."""
    expectation = SpanExpectation(
        match=SpanMatch(attributes={}, kind="CLIENT"),
        count=1,
        attributes={},
    )

    for spelling in ("client", "CLIENT", "SPAN_KIND_CLIENT"):
        assert (
            check(
                scenario(spans=(expectation,)),
                window([captured_span(kind=spelling)]),
            )
            == []
        )


@pytest.mark.parametrize(
    ("matcher", "values", "ok"),
    [
        (AttributeMatcher(equals="a"), ["a", "a"], True),
        (AttributeMatcher(equals="a"), ["a", "b"], False),
        (AttributeMatcher(present=True), ["a", "b"], True),
        (AttributeMatcher(present=False), ["a"], False),
        (AttributeMatcher(distinct=2), ["a", "b"], True),
        (AttributeMatcher(distinct=2), ["a", "a"], False),
    ],
)
def test_attribute_matchers(
    matcher: AttributeMatcher, values: list[str], ok: bool
) -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=len(values),
        attributes={"gen_ai.tool.name": matcher},
    )
    captured = window(
        [
            captured_span(
                **{"gen_ai.operation.name": "chat", "gen_ai.tool.name": value}
            )
            for value in values
        ]
    )

    assert (check(scenario(spans=(expectation,)), captured) == []) is ok


def test_present_false_passes_when_attribute_is_absent() -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=1,
        attributes={"server.address": AttributeMatcher(present=False)},
    )
    captured = window([captured_span(**{"gen_ai.operation.name": "chat"})])

    assert check(scenario(spans=(expectation,)), captured) == []


def test_a_malformed_but_present_value_satisfies_presence() -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=1,
        attributes={"server.port": AttributeMatcher(present=True)},
    )
    captured = window(
        [
            captured_span(
                **{
                    "gen_ai.operation.name": "chat",
                    "server.port": "malformed",
                }
            )
        ]
    )

    assert check(scenario(spans=(expectation,)), captured) == []


def test_list_valued_attributes_are_comparable() -> None:
    """Weaver reports list values; they must not blow up the distinct count."""
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=2,
        attributes={
            "gen_ai.response.finish_reasons": AttributeMatcher(distinct=1)
        },
    )
    captured = window(
        [
            captured_span(
                **{
                    "gen_ai.operation.name": "chat",
                    "gen_ai.response.finish_reasons": ["stop"],
                }
            )
            for _ in range(2)
        ]
    )

    assert check(scenario(spans=(expectation,)), captured) == []


@pytest.mark.parametrize("signal", ["metrics", "events"])
def test_declared_signal_lists_are_exact(signal: str) -> None:
    """A declared metric or event list fails both ways — same rule for both."""
    emitted = (
        "gen_ai.client.operation.duration"
        if signal == "metrics"
        else "gen_ai.client.inference.operation.details"
    )
    captured = window(
        metrics=("gen_ai.client.operation.duration",),
        events=("gen_ai.client.inference.operation.details",),
    )

    assert check(scenario(**{signal: (emitted,)}), captured) == []

    (missing,) = check(scenario(**{signal: (emitted, "other")}), captured)
    assert "not emitted" in missing

    (extra,) = check(scenario(**{signal: ()}), captured)
    assert "undeclared" in extra


def test_an_optional_metric_is_neither_required_nor_undeclared() -> None:
    """What only some actions record, without loosening the rest."""
    declared = scenario(
        metrics=("gen_ai.client.operation.duration",),
        optional_metrics=("gen_ai.client.token.usage",),
    )

    assert (
        check(
            declared,
            window(metrics=("gen_ai.client.operation.duration",)),
        )
        == []
    )
    assert (
        check(
            declared,
            window(
                metrics=(
                    "gen_ai.client.operation.duration",
                    "gen_ai.client.token.usage",
                )
            ),
        )
        == []
    )

    (extra,) = check(
        declared,
        window(
            metrics=(
                "gen_ai.client.operation.duration",
                "gen_ai.server.request.duration",
            )
        ),
    )
    assert "undeclared metrics emitted: ['gen_ai.server.request.duration']" in (
        extra
    )


def test_span_events_do_not_count_as_otlp_log_events() -> None:
    captured = window([captured_span()])

    assert check(scenario(events=()), captured) == []


def test_undeclared_violation_fails() -> None:
    report = WeaverReport(
        violations=[
            {
                "id": "genai_expected_attribute_missing",
                "context": {"operation": "chat"},
                "message": "server.address is missing",
            }
        ]
    )

    findings = check_package_violations(package_spec(), report, complete=True)
    (failure,) = findings.violations
    assert failure == (
        "[genai_expected_attribute_missing] server.address is missing"
    )
    assert findings.failures == []


def test_declared_violation_is_accepted_then_required() -> None:
    declared = ExpectedViolation(
        id="genai_expected_attribute_missing",
        context={"operation": "chat"},
        reason="the SDK does not expose it",
    )
    spec = package_spec((declared,))
    reported = {
        "id": "genai_expected_attribute_missing",
        "context": {"operation": "chat"},
    }

    findings = check_package_violations(
        spec, WeaverReport(violations=[reported]), complete=True
    )
    assert findings.failures == []
    assert findings.violations == []

    findings = check_package_violations(spec, WeaverReport(), complete=True)
    (failure,) = findings.failures
    assert "no longer reported" in failure


def test_violation_context_must_match_in_full() -> None:
    """Same advice id, different context — a different finding."""
    declared = ExpectedViolation(
        id="genai_expected_attribute_missing",
        context={"operation": "chat", "missing_attribute": "server.address"},
        reason="known",
    )
    report = WeaverReport(
        violations=[
            {
                "id": "genai_expected_attribute_missing",
                "context": {
                    "operation": "chat",
                    "missing_attribute": "server.port",
                },
            }
        ]
    )

    findings = check_package_violations(
        package_spec((declared,)), report, complete=True
    )
    assert len(findings.failures) == 1
    assert len(findings.violations) == 1


def test_partial_run_does_not_require_declared_violations() -> None:
    declared = ExpectedViolation(
        id="genai_expected_attribute_missing",
        context=None,
        reason="known",
    )

    findings = check_package_violations(
        package_spec((declared,)), WeaverReport(), complete=False
    )

    assert findings.failures == []
    assert findings.violations == []


def test_coverage_reduces_a_run(tmp_path: Path) -> None:
    write_capture_report(
        tmp_path,
        "inference",
        span_sample(
            **{
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": "gpt-4o-mini",
            }
        ),
        metrics=("gen_ai.client.operation.duration",),
        events=("custom.event",),
    )
    spec = PackageSpec(
        instrumented_library="demo",
        instrumentation_library="demo-instrumentation",
        directory=tmp_path,
        env={},
        weaver=WeaverSpec(),
        server=ServerSpec(),
        setup=None,
        scenarios={"inference": scenario(spans=(CHAT,))},
    )

    assert coverage(tmp_path, spec) == {
        "spans": [
            {
                "match": {"attributes": {"gen_ai.operation.name": "chat"}},
                "attributes": [
                    "gen_ai.operation.name",
                    "gen_ai.request.model",
                ],
            }
        ],
        "metrics": ["gen_ai.client.operation.duration"],
        "events": ["custom.event"],
        "findings": [],
    }


def test_coverage_records_the_violations_a_run_drew(tmp_path: Path) -> None:
    """Deduplicated, and only violations: lesser advice isn't a finding."""
    said = {
        "id": "expected_attribute_missing",
        "level": "violation",
        "message": "missing server.address",
        "context": {"attr": "server.address"},
    }
    (tmp_path / WEAVER_REPORT).write_text(
        json.dumps(
            {
                "live_check_result": {
                    "all_advice": [
                        said,
                        said,
                        {
                            "id": "not_stable",
                            "level": "improvement",
                            "message": "not recorded",
                            "context": None,
                        },
                    ]
                }
            }
        )
    )
    spec = PackageSpec(
        instrumented_library="demo",
        instrumentation_library="demo-instrumentation",
        directory=tmp_path,
        env={},
        weaver=WeaverSpec(),
        server=ServerSpec(),
        setup=None,
        scenarios={
            "inference": scenario(spans=()),
            "streaming": scenario(spans=()),
        },
    )

    assert coverage(tmp_path, spec)["findings"] == [
        {
            "id": "expected_attribute_missing",
            "message": "missing server.address",
            "context": {"attr": "server.address"},
        },
    ]


def test_a_violation_without_context_accepts_every_finding_with_that_id() -> (
    None
):
    declared = ExpectedViolation(
        id="missing_attribute",
        context=None,
        reason="the implementation's own attribute namespace",
    )
    report = WeaverReport(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}},
            {"id": "missing_attribute", "context": {"attribute_key": "llm.b"}},
        ]
    )

    findings = check_package_violations(
        package_spec((declared,)), report, complete=True
    )

    assert findings.failures == []
    assert findings.violations == []


def test_a_violation_without_context_does_not_accept_other_ids() -> None:
    declared = ExpectedViolation(
        id="missing_attribute", context=None, reason="known"
    )
    report = WeaverReport(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}},
            {
                "id": "genai_span_kind_unexpected",
                "context": {"kind": "internal"},
            },
        ]
    )

    findings = check_package_violations(
        package_spec((declared,)), report, complete=True
    )
    (failure,) = findings.violations

    assert "genai_span_kind_unexpected" in failure
    assert findings.failures == []


def test_an_empty_context_still_means_a_finding_carried_none() -> None:
    """`context: {}` is a declaration, not an omission."""
    declared = ExpectedViolation(
        id="missing_attribute", context={}, reason="known"
    )
    report = WeaverReport(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}}
        ]
    )

    findings = check_package_violations(
        package_spec((declared,)), report, complete=True
    )

    assert len(findings.failures) == 1
    assert len(findings.violations) == 1


def _report_with(*samples: dict[str, Any]) -> str:
    return json.dumps({"samples": list(samples), "statistics": {}})


def _package(tmp_path: Path, **scenario_kwargs: Any) -> PackageSpec:
    return PackageSpec(
        instrumented_library="demo",
        instrumentation_library="demo-instrumentation",
        directory=tmp_path,
        env={},
        weaver=WeaverSpec(),
        server=ServerSpec(),
        setup=None,
        scenarios={"inference": scenario(**scenario_kwargs)},
    )


def test_coverage_records_spans_no_expectation_declared(
    tmp_path: Path,
) -> None:
    """A scenario declaring nothing still leaves a record of what it emitted.

    Measuring an implementation you don't own is the case with no
    expectations at all; reducing that to nothing would defeat the point.
    """
    write_capture_report(
        tmp_path,
        "inference",
        span_sample(kind="internal", **{"llm.model_name": "gpt-4o-mini"}),
    )

    assert coverage(tmp_path, _package(tmp_path))["spans"] == [
        {"match": {"kind": "internal"}, "attributes": ["llm.model_name"]}
    ]


def test_coverage_keeps_undeclared_spans_apart_from_declared_ones(
    tmp_path: Path,
) -> None:
    write_capture_report(
        tmp_path,
        "inference",
        span_sample(**{"gen_ai.operation.name": "chat"}),
        span_sample(kind="internal", **{"custom.attribute": "x"}),
    )

    assert coverage(tmp_path, _package(tmp_path, spans=(CHAT,)))["spans"] == [
        {
            "match": {"attributes": {"gen_ai.operation.name": "chat"}},
            "attributes": ["gen_ai.operation.name"],
        },
        {"match": {"kind": "internal"}, "attributes": ["custom.attribute"]},
    ]


def test_mapping_only_expectation_does_not_enforce_exact_validation() -> None:
    # A mapping-only expectation (count is None)
    mapping = SpanExpectation(
        match=SpanMatch(
            attributes={"gen_ai.operation.name": "chat"},
            type="gen_ai.inference.client",
        ),
        count=None,
    )
    # The scenario has ONLY mapping-only expectations
    spec = scenario(spans=(mapping,))

    captured = window(
        [
            captured_span(**{"gen_ai.operation.name": "chat"}),
            captured_span(name="other_span", **{"custom.attr": "value"}),
        ]
    )

    assert check(spec, captured) == []
