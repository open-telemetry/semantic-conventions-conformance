# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Classifying GenAI spans, and what the resolved coverage model holds.

The model is what weaver resolved out of the pinned registry: every span type,
metric and event it declares. A provider refinement keeps its own id, so what
``openai.inference.client`` adds is not coverage of ``gen_ai.inference.client``.
How a run is *reduced* against that model belongs to the runner; see
``tools/runner/tests/test_semconv.py``.

Needs the pinned registry and the model resolved out of it.
"""

from __future__ import annotations

import pytest

from genai_conformance import DOMAIN
from opentelemetry.conformance._report import Observed
from opentelemetry.conformance._semconv import _reduce


@pytest.fixture(name="model", scope="module")
def _model():
    try:
        return DOMAIN.coverage_model
    except (OSError, RuntimeError) as error:
        pytest.skip(f"coverage model not available: {error}")


@pytest.fixture(name="classify_span", scope="module")
def _classify_span(model):
    return DOMAIN.classifier(model)


@pytest.fixture(name="mcp_classify_span", scope="module")
def _mcp_classify_span():
    """Classify without requiring the externally resolved registry model."""
    return DOMAIN.classifier(
        {
            "spans": {
                "gen_ai.execute_tool.internal": {"kind": "internal"},
                "mcp.client": {"kind": "client"},
                "mcp.server": {"kind": "server"},
            }
        }
    )


@pytest.fixture(name="reduce_for")
def _reduce_for(model):
    """Reduce a run that emitted the given signals carrying every attribute."""

    def build(span_types=(), events=(), metrics=(), entities=()):
        def signals(names, section):
            return {
                name: set(model[section][name]["attributes"]) for name in names
            }

        resources = {
            attr
            for name in entities
            for part in ("identity", "description")
            for attr in model.get("entities", {}).get(name, {}).get(part, {})
        }

        return _reduce(
            Observed(
                spans=signals(span_types, "spans"),
                events=signals(events, "events"),
                metrics=signals(metrics, "metrics"),
                resources=resources,
            ),
            model,
        )

    return build


def test_the_operation_name_names_the_span_type(classify_span) -> None:
    assert classify_span(
        "chat gpt-4", "client", {"gen_ai.operation.name": "chat"}
    ) == {"gen_ai.inference.client"}


@pytest.mark.parametrize(
    ("span_kind", "span_type"),
    [("client", "mcp.client"), ("server", "mcp.server")],
)
def test_mcp_method_takes_precedence_over_genai_compatibility_attributes(
    mcp_classify_span, span_kind, span_type
) -> None:
    assert mcp_classify_span(
        "tools/call get_weather",
        span_kind,
        {
            "mcp.method.name": "tools/call",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "get_weather",
        },
    ) == {span_type}


def test_mcp_method_does_not_reclassify_an_internal_tool_span(
    mcp_classify_span,
) -> None:
    assert mcp_classify_span(
        "execute_tool get_weather",
        "internal",
        {
            "mcp.method.name": "tools/call",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "get_weather",
        },
    ) == {"gen_ai.execute_tool.internal"}


def test_mcp_method_falls_back_when_registry_has_no_mcp_span_type() -> None:
    classify_span = DOMAIN.classifier(
        {
            "spans": {
                "gen_ai.execute_tool.internal": {"kind": "internal"},
            }
        }
    )

    assert classify_span(
        "tools/call get_weather",
        "client",
        {
            "mcp.method.name": "tools/call",
            "gen_ai.operation.name": "execute_tool",
        },
    ) == {"gen_ai.execute_tool.internal"}


def test_a_span_without_an_operation_name_is_identified_by_its_attributes(
    classify_span,
) -> None:
    assert classify_span(
        "tool", "internal", {"gen_ai.tool.name": "get_weather"}
    ) == {"gen_ai.execute_tool.internal"}


def test_the_operation_name_wins_over_identifying_attributes(
    classify_span,
) -> None:
    """An inference span holding gen_ai.agent.id is not an agent invocation."""
    classified = classify_span(
        "chat gpt-4",
        "client",
        {"gen_ai.operation.name": "chat", "gen_ai.agent.id": "a1"},
    )

    assert classified == {"gen_ai.inference.client"}


def test_span_kind_tells_the_two_invoke_agent_types_apart(
    classify_span,
) -> None:
    attributes = {"gen_ai.operation.name": "invoke_agent"}

    assert classify_span("", "client", attributes) == {
        "gen_ai.invoke_agent.client"
    }
    assert classify_span("", "internal", attributes) == {
        "gen_ai.invoke_agent.internal"
    }


def test_a_span_of_no_known_type_is_classified_as_nothing(
    classify_span,
) -> None:
    assert (
        classify_span("GET /", "client", {"http.request.method": "GET"})
        == set()
    )


def test_provider_attributes_are_not_coverage_of_the_type_they_refine(
    model,
) -> None:
    """openai.inference.client is a refinement, not part of the general type."""
    inference = model["spans"]["gen_ai.inference.client"]["attributes"]

    assert not [name for name in inference if name.startswith("openai.")]


def test_the_base_conventions_come_through(reduce_for) -> None:
    data = reduce_for(span_types=["gen_ai.inference.client"])

    assert {"gen_ai.operation.name", "gen_ai.request.model"} <= set(
        data["spans"]["gen_ai.inference.client"]
    )


def test_every_declared_metric_is_recordable(model, reduce_for) -> None:
    """Upstream hand-lists two of twelve; a coverage artifact wants them all."""
    declared = [
        name for name in model["metrics"] if name.startswith("gen_ai.")
    ]

    recorded = reduce_for(metrics=declared)["metrics"]

    assert set(recorded) == set(declared)
    assert "gen_ai.operation.name" in recorded["gen_ai.client.token.usage"]


def test_every_declared_event_is_recordable(model, reduce_for) -> None:
    declared = [name for name in model["events"] if name.startswith("gen_ai.")]

    recorded = reduce_for(events=declared)["events"]

    assert set(recorded) == set(declared)
    assert "gen_ai.client.operation.exception" in recorded


def test_every_declared_entity_is_recordable(model, reduce_for) -> None:
    declared = [
        name
        for name in model.get("entities", {})
        if name.startswith("gen_ai.")
    ]

    recorded = reduce_for(entities=declared)["entities"]

    assert set(recorded) == set(declared)
    for name in declared:
        assert "identity" in recorded[name]
        assert "description" in recorded[name]
