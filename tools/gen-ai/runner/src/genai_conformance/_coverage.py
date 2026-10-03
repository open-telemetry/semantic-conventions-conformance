# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""How to recognise a GenAI span type.

A run is reduced by asking, per registry span type, which of that type's
attributes were present. The registry declares a type's attributes but not how
to spot one — every GenAI span type carries the whole ``gen_ai.operation.name``
enum — so that knowledge lives here, and it is the only thing this domain has
to supply beyond its pin and its policies.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

# Which operation names belong to which span type.
_OPERATION_NAMES = {
    "gen_ai.create_agent.client": {"create_agent"},
    "gen_ai.embeddings.client": {"embeddings"},
    "gen_ai.execute_tool.internal": {"execute_tool"},
    "gen_ai.fetch_response.client": {"fetch_response"},
    "gen_ai.generate_live_content.client": {"generate_live_content"},
    "gen_ai.inference.client": {"chat", "generate_content", "text_completion"},
    "gen_ai.invoke_agent.client": {"invoke_agent"},
    "gen_ai.invoke_agent.internal": {"invoke_agent"},
    "gen_ai.invoke_workflow.internal": {"invoke_workflow"},
    "gen_ai.memory.client": {
        "create_memory",
        "create_memory_store",
        "delete_memory",
        "delete_memory_store",
        "search_memory",
        "update_memory",
        "upsert_memory",
    },
    "gen_ai.plan.internal": {"plan"},
    "gen_ai.retrieval.client": {"retrieval"},
    "gen_ai.user_input.client": {"user_input"},
}

# What identifies a span that omits the operation name. create_agent and plan
# share gen_ai.agent.{id,name} with invoke_agent, so nothing identifies them
# but the operation name.
_IDENTIFYING_ATTRIBUTES = {
    "gen_ai.embeddings.client": {
        "gen_ai.embeddings.dimension.count",
        "gen_ai.request.encoding_formats",
    },
    "gen_ai.execute_tool.internal": {
        "gen_ai.tool.call.id",
        "gen_ai.tool.name",
    },
    "gen_ai.invoke_agent.client": {"gen_ai.agent.id", "gen_ai.agent.name"},
    "gen_ai.invoke_agent.internal": {"gen_ai.agent.id", "gen_ai.agent.name"},
    "gen_ai.invoke_workflow.internal": {"gen_ai.workflow.name"},
    "gen_ai.retrieval.client": {"gen_ai.data_source.id"},
}


def classifier(
    coverage_model: Mapping[str, Any],
) -> Callable[[str, str, Mapping[str, object]], set[str]]:
    """Build the classifier, reading span kinds out of the coverage model."""

    def classify_span(
        span_name: str, span_kind: str, attributes: Mapping[str, object]
    ) -> set[str]:
        """The span types a span belongs to.

        ``gen_ai.operation.name`` names the type when it is set. A span that
        omits it is recognised by the attributes only its type carries — but a
        span that names its operation *is* that operation, whatever else it
        carries, so an inference span holding ``gen_ai.agent.id`` is not an
        agent invocation.

        ``span_name`` is unused; it is accepted to match the runner's
        signature.
        """
        del span_name
        operation = str(attributes.get("gen_ai.operation.name", "")).lower()
        present = {
            name for name, value in attributes.items() if value is not None
        }

        named = {
            span_type
            for span_type, operations in _OPERATION_NAMES.items()
            if operation in operations
        }
        matched = named or {
            span_type
            for span_type, identifying in _IDENTIFYING_ATTRIBUTES.items()
            if identifying & present
        }

        # Span kind separates otherwise identical types, e.g. an agent invoked
        # over the wire (client) from one running in-process (internal).
        spans = coverage_model["spans"]
        of_this_kind = {
            span_type
            for span_type in matched
            if spans.get(span_type, {}).get("kind") == span_kind.lower()
        }
        return of_this_kind or matched

    return classify_span
