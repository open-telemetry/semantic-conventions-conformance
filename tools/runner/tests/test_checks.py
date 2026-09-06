# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Expectations vs. a weaver report.

The report is fed in as the plain dict weaver produces, so these cover the
check logic without weaver, a mock server or a scenario process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from opentelemetry.conformance._checks import check as _check
from opentelemetry.conformance._coverage import coverage
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


class Report(dict[str, Any]):
    """Stands in for ``LiveCheckReport``: a dict plus a ``violations`` list."""

    def __init__(
        self,
        samples: list[dict[str, Any]] | None = None,
        statistics: dict[str, Any] | None = None,
        violations: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(samples=samples or [], statistics=statistics or {})
        self.violations = violations or []


def check(spec: ScenarioSpec, report: Any) -> list[str]:
    """Both kinds of finding; the split has its own tests below."""
    return _check(spec, report).all()


def scenario(**kwargs: Any) -> ScenarioSpec:
    defaults: dict[str, Any] = {
        "name": "inference",
        "directory": Path("."),
        "env": {},
        "run": ("python", "inference.py"),
        "spans": None,
        "metrics": None,
        "events": None,
        "expected_violations": (),
    }
    return ScenarioSpec(**{**defaults, **kwargs})


CHAT = SpanExpectation(
    match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
    count=1,
    attributes={},
)


def test_no_expectations_passes_on_anything() -> None:
    report = Report(
        samples=[span_sample(**{"gen_ai.operation.name": "chat"})],
        statistics={"seen_registry_metrics": {"gen_ai.client.token.usage": 3}},
    )

    assert check(scenario(), report) == []


def test_span_count_must_be_exact() -> None:
    report = Report(
        samples=[
            span_sample(**{"gen_ai.operation.name": "chat"}),
            span_sample(**{"gen_ai.operation.name": "chat"}),
        ]
    )

    (failure,) = check(scenario(spans=(CHAT,)), report)
    assert "expected 1 span(s)" in failure
    assert "saw 2" in failure


def test_undeclared_span_fails() -> None:
    report = Report(
        samples=[
            span_sample(**{"gen_ai.operation.name": "chat"}),
            span_sample(
                name="execute_tool lookup",
                **{"gen_ai.operation.name": "execute_tool"},
            ),
        ]
    )

    (failure,) = check(scenario(spans=(CHAT,)), report)
    assert "1 undeclared span(s)" in failure
    assert "execute_tool lookup" in failure


def test_match_on_kind() -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={}, kind="CLIENT"),
        count=1,
        attributes={},
    )

    assert check(scenario(spans=(expectation,)), Report([span_sample()])) == []
    assert (
        check(
            scenario(spans=(expectation,)),
            Report([span_sample(kind="SERVER")]),
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
                Report([span_sample(kind=spelling)]),
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
    report = Report(
        [
            span_sample(
                **{"gen_ai.operation.name": "chat", "gen_ai.tool.name": value}
            )
            for value in values
        ]
    )

    assert (check(scenario(spans=(expectation,)), report) == []) is ok


def test_present_false_passes_when_attribute_is_absent() -> None:
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=1,
        attributes={"server.address": AttributeMatcher(present=False)},
    )
    report = Report([span_sample(**{"gen_ai.operation.name": "chat"})])

    assert check(scenario(spans=(expectation,)), report) == []


def test_a_rejected_value_does_not_satisfy_an_expectation() -> None:
    """Weaver rejected the value, so the attribute did not really arrive."""
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=1,
        attributes={"server.port": AttributeMatcher(present=True)},
    )
    sample = span_sample(**{"gen_ai.operation.name": "chat"})
    sample["span"]["attributes"].append(
        {
            "name": "server.port",
            "value": "8080",
            "live_check_result": {"all_advice": [{"id": "type_mismatch"}]},
        }
    )

    (failure,) = check(scenario(spans=(expectation,)), Report([sample]))
    assert "server.port" in failure


def test_list_valued_attributes_are_comparable() -> None:
    """Weaver reports list values; they must not blow up the distinct count."""
    expectation = SpanExpectation(
        match=SpanMatch(attributes={"gen_ai.operation.name": "chat"}),
        count=2,
        attributes={
            "gen_ai.response.finish_reasons": AttributeMatcher(distinct=1)
        },
    )
    report = Report(
        [
            span_sample(
                **{
                    "gen_ai.operation.name": "chat",
                    "gen_ai.response.finish_reasons": ["stop"],
                }
            )
            for _ in range(2)
        ]
    )

    assert check(scenario(spans=(expectation,)), report) == []


@pytest.mark.parametrize("signal", ["metrics", "events"])
def test_declared_signal_lists_are_exact(signal: str) -> None:
    """A declared metric or event list fails both ways — same rule for both."""
    statistics = {
        "seen_registry_metrics": {"gen_ai.client.operation.duration": 1},
        "seen_registry_events": {
            "gen_ai.client.inference.operation.details": 1
        },
    }
    emitted = (
        "gen_ai.client.operation.duration"
        if signal == "metrics"
        else "gen_ai.client.inference.operation.details"
    )
    report = Report(statistics=statistics)

    assert check(scenario(**{signal: (emitted,)}), report) == []

    (missing,) = check(scenario(**{signal: (emitted, "other")}), report)
    assert "not emitted" in missing

    (extra,) = check(scenario(**{signal: ()}), report)
    assert "undeclared" in extra


def test_zero_count_signals_are_not_seen() -> None:
    report = Report(statistics={"seen_registry_metrics": {"never.emitted": 0}})

    assert check(scenario(metrics=()), report) == []


def test_undeclared_violation_fails() -> None:
    report = Report(
        violations=[
            {
                "id": "genai_expected_attribute_missing",
                "context": {"operation": "chat"},
                "message": "server.address is missing",
            }
        ]
    )

    (failure,) = check(scenario(), report)
    assert failure == (
        "[genai_expected_attribute_missing] server.address is missing"
    )


def test_declared_violation_is_accepted_then_required() -> None:
    declared = ExpectedViolation(
        id="genai_expected_attribute_missing",
        context={"operation": "chat"},
        reason="the SDK does not expose it",
    )
    spec = scenario(expected_violations=(declared,))
    reported = {
        "id": "genai_expected_attribute_missing",
        "context": {"operation": "chat"},
    }

    assert check(spec, Report(violations=[reported])) == []

    (failure,) = check(spec, Report(violations=[]))
    assert "no longer reported" in failure


def test_violation_context_must_match_in_full() -> None:
    """Same advice id, different context — a different finding."""
    declared = ExpectedViolation(
        id="genai_expected_attribute_missing",
        context={"operation": "chat", "missing_attribute": "server.address"},
        reason="known",
    )
    report = Report(
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

    failures = check(scenario(expected_violations=(declared,)), report)
    assert (
        len(failures) == 2
    )  # the undeclared one, and the declared one missing


def test_violations_are_kept_apart_from_failures() -> None:
    report = Report(
        samples=[],
        violations=[{"id": "genai_expected_attribute_missing"}],
    )

    findings = _check(scenario(spans=(CHAT,)), report)
    (mismatch,) = findings.failures
    assert "matching" in mismatch
    # No message and no context: the id is all there is to say.
    assert findings.violations == ["[genai_expected_attribute_missing]"]


def test_coverage_reduces_a_run(tmp_path: Path) -> None:
    (tmp_path / "inference.json").write_text(
        json.dumps(
            {
                "samples": [
                    span_sample(
                        **{
                            "gen_ai.operation.name": "chat",
                            "gen_ai.request.model": "gpt-4o-mini",
                        }
                    )
                ],
                "statistics": {
                    "seen_registry_metrics": {
                        "gen_ai.client.operation.duration": 1
                    },
                    "seen_non_registry_events": {"custom.event": 1},
                },
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
    for name in ("inference", "streaming"):
        (tmp_path / f"{name}.json").write_text(
            json.dumps(
                {
                    "samples": [
                        {"live_check_result": {"all_advice": [said]}},
                        {
                            "live_check_result": {
                                "all_advice": [
                                    said,
                                    {
                                        "id": "not_stable",
                                        "level": "improvement",
                                        "message": "not recorded",
                                        "context": None,
                                    },
                                ]
                            }
                        },
                    ],
                    "statistics": {},
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
    """One gap seen many times is declared once."""
    declared = ExpectedViolation(
        id="missing_attribute",
        context=None,
        reason="the implementation's own attribute namespace",
    )
    spec = scenario(expected_violations=(declared,))
    report = Report(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}},
            {"id": "missing_attribute", "context": {"attribute_key": "llm.b"}},
        ]
    )

    assert check(spec, report) == []


def test_a_violation_without_context_still_fails_once_the_class_empties(
) -> None:
    """Bulk or not, a suppression mustn't outlive the gap that caused it."""
    declared = ExpectedViolation(
        id="missing_attribute", context=None, reason="known"
    )
    spec = scenario(expected_violations=(declared,))

    (failure,) = check(spec, Report(violations=[]))

    assert "no longer reported" in failure
    assert "any context" in failure


def test_a_violation_without_context_does_not_accept_other_ids() -> None:
    declared = ExpectedViolation(
        id="missing_attribute", context=None, reason="known"
    )
    spec = scenario(expected_violations=(declared,))
    report = Report(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}},
            {"id": "genai_span_kind_unexpected", "context": {"kind": "internal"}},
        ]
    )

    (failure,) = check(spec, report)

    assert "genai_span_kind_unexpected" in failure


def test_an_empty_context_still_means_a_finding_carried_none() -> None:
    """`context: {}` is a declaration, not an omission."""
    declared = ExpectedViolation(
        id="missing_attribute", context={}, reason="known"
    )
    spec = scenario(expected_violations=(declared,))
    report = Report(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}}
        ]
    )

    assert check(spec, report) != []


def test_a_package_violation_suppresses_in_every_scenario() -> None:
    spec = scenario(
        inherited_violations=(
            ExpectedViolation(
                id="missing_attribute",
                context=None,
                reason="declared once for the package",
            ),
        )
    )
    report = Report(
        violations=[
            {"id": "missing_attribute", "context": {"attribute_key": "llm.a"}}
        ]
    )

    assert check(spec, report) == []


def test_a_package_violation_no_scenario_reaches_is_not_a_failure() -> None:
    """It describes a gap in general, not a promise about each scenario."""
    spec = scenario(
        inherited_violations=(
            ExpectedViolation(
                id="missing_attribute", context=None, reason="package-wide"
            ),
        )
    )

    assert check(spec, Report(violations=[])) == []


def test_a_scenario_violation_is_still_required_alongside_package_ones() -> (
    None
):
    spec = scenario(
        expected_violations=(
            ExpectedViolation(
                id="genai_span_kind_unexpected",
                context={"kind": "internal"},
                reason="this scenario's own",
            ),
        ),
        inherited_violations=(
            ExpectedViolation(
                id="missing_attribute", context=None, reason="package-wide"
            ),
        ),
    )

    (failure,) = check(spec, Report(violations=[]))

    assert "genai_span_kind_unexpected" in failure
    assert "no longer reported" in failure


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
    (tmp_path / "inference.json").write_text(
        _report_with(
            span_sample(kind="internal", **{"llm.model_name": "gpt-4o-mini"})
        )
    )

    assert coverage(tmp_path, _package(tmp_path))["spans"] == [
        {"match": {"kind": "internal"}, "attributes": ["llm.model_name"]}
    ]


def test_coverage_keeps_undeclared_spans_apart_from_declared_ones(
    tmp_path: Path,
) -> None:
    (tmp_path / "inference.json").write_text(
        _report_with(
            span_sample(**{"gen_ai.operation.name": "chat"}),
            span_sample(kind="internal", **{"custom.attribute": "x"}),
        )
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

    report = Report(
        samples=[
            span_sample(**{"gen_ai.operation.name": "chat"}),
            span_sample(name="other_span", **{"custom.attr": "value"}),  # undeclared span
        ]
    )

    # It should pass without raising undeclared span error
    assert check(spec, report) == []
