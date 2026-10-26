# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Instrumentation scope expectations are recorded as weaver findings."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from http_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver
from opentelemetry.conformance._scope_policy import render
from opentelemetry.conformance._spec import (
    AttributeMatcher,
    InstrumentationScopeExpectation,
    SpanExpectation,
    SpanMatch,
)


def test_scope_findings_are_in_weaver_report(tmp_path: Path) -> None:
    try:
        check_weaver()
        registry = DOMAIN.registry
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"scope policy test unavailable: {error}")

    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "instrumentation_scope_validation.rego").write_text(
        render(None),
        encoding="utf-8",
    )
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "instrumentation_scope": {
                        "name": "has-schema",
                        "version": "1.0.0",
                        "schema_url": "https://example.test/schema/1.0.0",
                        "attributes": [],
                    }
                },
                {
                    "instrumentation_scope": {
                        "name": "missing-schema",
                        "version": "1.0.0",
                        "schema_url": "",
                        "attributes": [],
                    }
                },
                {
                    "span": {
                        "name": "missing-scope",
                        "kind": "client",
                        "attributes": [],
                    }
                },
            ]
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / "report"

    result = subprocess.run(
        [
            "weaver",
            "registry",
            "live-check",
            "--quiet",
            "--registry",
            str(registry),
            "--input-source",
            str(input_path),
            "--advice-policies",
            str(policies),
            "--format",
            "json",
            "--fail-on",
            "none",
            "--no-stream",
            "--output",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    report: dict[str, Any] = json.loads(
        (report_dir / "live_check.json").read_text(encoding="utf-8")
    )
    scopes = {
        scope["name"]: scope["live_check_result"]["all_advice"]
        for sample in report["samples"]
        if (scope := sample.get("instrumentation_scope")) is not None
    }
    assert scopes["has-schema"] == []
    assert [finding["id"] for finding in scopes["missing-schema"]] == [
        "instrumentation_scope_schema_url_missing"
    ]
    assert scopes["missing-schema"][0]["message"] == (
        "Instrumentation scope 'missing-schema' does not have schema_url."
    )
    unscoped_span = next(
        sample["span"]
        for sample in report["samples"]
        if sample.get("span", {}).get("name") == "missing-scope"
    )
    findings = unscoped_span["live_check_result"]["all_advice"]
    assert {finding["id"]: finding["message"] for finding in findings} == {
        "instrumentation_scope_name_missing": (
            "Instrumentation scope '<missing>' does not have name."
        ),
        "instrumentation_scope_schema_url_missing": (
            "Instrumentation scope '<missing>' does not have schema_url."
        ),
    }
    assert all(
        finding["context"] == {"actual": None, "expected": {"present": True}}
        and finding["level"] == "violation"
        and finding["signal_name"] == "missing-scope"
        and finding["signal_type"] == "span"
        and finding["type"] == "PolicyFinding"
        for finding in findings
    )


def test_signal_scope_expectation_uses_owning_scope(tmp_path: Path) -> None:
    try:
        check_weaver()
        registry = DOMAIN.registry
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"scope policy test unavailable: {error}")
    import opentelemetry.exporter.otlp.proto.grpc.trace_exporter as trace_exporter  # noqa: PLC0415
    import opentelemetry.sdk.trace as sdk_trace  # noqa: PLC0415
    import opentelemetry.sdk.trace.export as sdk_trace_export  # noqa: PLC0415
    import opentelemetry.trace as trace  # noqa: PLC0415
    from opentelemetry.conformance._weaver import (  # noqa: PLC0415
        WeaverLiveCheck,
    )

    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "instrumentation_scope_validation.rego").write_text(
        render(
            (
                SpanExpectation(
                    match=SpanMatch(
                        attributes={"operation": "chat"}, kind="CLIENT"
                    ),
                    instrumentation_scope=InstrumentationScopeExpectation(
                        name=AttributeMatcher(equals="expected-scope"),
                        schema_url=AttributeMatcher(present=False),
                    ),
                ),
            ),
        ),
        encoding="utf-8",
    )
    weaver = WeaverLiveCheck(
        registry=str(registry), policies_dir=str(policies)
    ).start()
    try:
        provider = sdk_trace.TracerProvider()
        provider.add_span_processor(
            sdk_trace_export.SimpleSpanProcessor(
                trace_exporter.OTLPSpanExporter(
                    endpoint=weaver.otlp_endpoint, insecure=True
                )
            )
        )
        tracer = provider.get_tracer(
            "actual-scope",
            "1.2.3",
            schema_url="https://example.test/schema/1.0.0",
        )
        with tracer.start_as_current_span(
            "matching-span", kind=trace.SpanKind.CLIENT
        ) as span:
            span.set_attribute("operation", "chat")
        with tracer.start_as_current_span(
            "non-matching-span", kind=trace.SpanKind.CLIENT
        ) as span:
            span.set_attribute("operation", "embeddings")
        provider.shutdown()
        report = weaver.end()
    finally:
        weaver.close()

    spans = {
        sample["span"]["name"]: sample["span"]
        for sample in report["samples"]
        if "span" in sample
    }
    findings = spans["matching-span"]["live_check_result"]["all_advice"]
    assert {finding["id"]: finding["context"] for finding in findings} == {
        "instrumentation_scope_name_mismatch": {
            "actual": "actual-scope",
            "expected": {"equals": "expected-scope"},
        },
        "unexpected_instrumentation_scope_schema_url": {
            "actual": "https://example.test/schema/1.0.0",
            "expected": {"present": False},
        },
    }
    assert spans["non-matching-span"]["live_check_result"]["all_advice"] == []


@pytest.mark.parametrize("field", ["name", "schema_url"])
@pytest.mark.parametrize("attached_scope", [False, True])
def test_absent_scope_field_overrides_default_for_matching_span(
    tmp_path: Path, field: str, attached_scope: bool
) -> None:
    try:
        check_weaver()
        registry = DOMAIN.registry
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"scope policy test unavailable: {error}")

    import grpc  # noqa: PLC0415

    from opentelemetry.conformance._weaver import (  # noqa: PLC0415
        WeaverLiveCheck,
    )
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (  # noqa: PLC0415
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc import (  # noqa: PLC0415
        TraceServiceStub,
    )
    from opentelemetry.proto.common.v1.common_pb2 import (  # noqa: PLC0415
        InstrumentationScope,
    )
    from opentelemetry.proto.trace.v1.trace_pb2 import (  # noqa: PLC0415
        ResourceSpans,
        ScopeSpans,
        Span,
    )
    policies = tmp_path / "policies"
    policies.mkdir()
    expectation = InstrumentationScopeExpectation(
        **{field: AttributeMatcher(present=False)}
    )
    (policies / "instrumentation_scope_validation.rego").write_text(
        render(
            (
                SpanExpectation(
                    match=SpanMatch(attributes={}, kind="CLIENT"),
                    instrumentation_scope=expectation,
                ),
            )
        ),
        encoding="utf-8",
    )
    scope_spans = ScopeSpans(
        spans=[
            Span(name="matching", kind=Span.SPAN_KIND_CLIENT),
            Span(name="unmatched", kind=Span.SPAN_KIND_SERVER),
        ]
    )
    if attached_scope:
        scope_spans.scope.CopyFrom(
            InstrumentationScope(name="" if field == "name" else "demo")
        )
        scope_spans.schema_url = (
            "" if field == "schema_url" else "https://example.test/schema"
        )

    weaver = WeaverLiveCheck(
        registry=str(registry), policies_dir=str(policies)
    ).start()
    try:
        with grpc.insecure_channel(
            weaver.otlp_endpoint.removeprefix("http://")
        ) as channel:
            TraceServiceStub(channel).Export(
                ExportTraceServiceRequest(
                    resource_spans=[ResourceSpans(scope_spans=[scope_spans])]
                ),
                timeout=10,
            )
        report = weaver.end()
    finally:
        weaver.close()

    spans = {
        sample["span"]["name"]: sample["span"]
        for sample in report["samples"]
        if "span" in sample
    }
    findings = {
        name: {
            finding["id"]
            for finding in span["live_check_result"]["all_advice"]
        }
        for name, span in spans.items()
    }
    other_field = "schema_url" if field == "name" else "name"
    other_defaults = (
        set()
        if attached_scope
        else {f"instrumentation_scope_{other_field}_missing"}
    )
    assert findings["matching"] == other_defaults
    assert findings["unmatched"] == other_defaults | {
        f"instrumentation_scope_{field}_missing"
    }
    assert all(
        not sample["instrumentation_scope"]["live_check_result"]["all_advice"]
        for sample in report["samples"]
        if "instrumentation_scope" in sample
    )
