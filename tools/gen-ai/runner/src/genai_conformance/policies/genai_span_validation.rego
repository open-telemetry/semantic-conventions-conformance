# Validates GenAI span shape beyond what weaver's semconv-registry-driven
# checks already enforce. The registry validates per-attribute requirements
# (name, type, presence) for spans matching its definitions; this file adds
# cross-cutting span-level invariants the registry can't easily express.
#
# Three classes of rules, all keyed on `gen_ai.operation.name`:
#
#   1. Span name format → `violation`
#      (`{operation_name} {request_model}` for inference / embeddings,
#      `{operation_name} {agent_name}` for invoke_agent / create_agent,
#      `{operation_name} {tool_name}` for execute_tool).
#
#   2. Per-operation expected attributes → `violation`
#      Combines `Required` (always must be set) and the always-emit subset
#      of `Recommended` (e.g. response model/id, token usage on inference)
#      into one manifest per operation. Sourced from the rendered tables in
#      semantic-conventions/docs/gen-ai/gen-ai-spans.md and
#      gen-ai-agent-spans.md (the MD flattens the YAML inheritance chain
#      via `extends:`, so it's the right place to source from).
#      `invoke_agent` is the one operation whose manifest also depends on
#      span kind: semconv defines separate internal (same-process) and
#      client (remote) spans, and only the client span carries server.*.
#
# The "set when known" Recommended subset (sampling parameters like
# `frequency_penalty`, `max_tokens`; provider-side caches; conditionally-
# emitted things like `gen_ai.response.time_to_first_chunk` for streaming)
# is deliberately NOT flagged here — those depend on user input or on the
# request shape and would produce noisy false positives. Cross-attribute
# conditional rules (e.g. "if streaming, response.time_to_first_chunk
# SHOULD be set") would also belong here.
#
# Required attributes are also flagged by weaver's registry-driven
# validation. Listing them here too is intentional: rego rules give us
# stable advice ids to grep for in reports and let us tighten the check
# regardless of how the registry classifies the gap.
#
# Span status and `error.type` are checked too, but not here: neither is about
# GenAI, so both live in the runner's own policies, loaded alongside this file.
#
# Attribute access: weaver hands rego a span sample where `attributes` is a
# **list** of `{name, value, type}` objects, not a dict — `_attr(name)`
# walks that list and returns the value (or `null` if absent).

package live_check_advice

import rego.v1

# ─── Operation classification ───────────────────────────────────────────────
#
# Mirrors the semconv `gen_ai.operation.name` enum
# (model/gen-ai/registry.yaml). When semconv adds a new operation, append it
# to the matching set below — or leave it out if the new operation has its
# own span definition with different conventions.

_inference_ops := {"chat", "generate_content", "text_completion"}

_embeddings_ops := {"embeddings"}

_tool_ops := {"execute_tool"}

_invoke_agent_ops := {"invoke_agent"}

_create_agent_ops := {"create_agent"}

# ─── Span name format (violation) ───────────────────────────────────────────

_span_name_keyed_attr["chat"]              := "gen_ai.request.model"
_span_name_keyed_attr["generate_content"]  := "gen_ai.request.model"
_span_name_keyed_attr["text_completion"]   := "gen_ai.request.model"
_span_name_keyed_attr["embeddings"]        := "gen_ai.request.model"
_span_name_keyed_attr["execute_tool"]      := "gen_ai.tool.name"
_span_name_keyed_attr["invoke_agent"]      := "gen_ai.agent.name"
_span_name_keyed_attr["create_agent"]      := "gen_ai.agent.name"
_span_name_keyed_attr["invoke_workflow"]   := "gen_ai.workflow.name"
_span_name_keyed_attr["retrieval"]         := "gen_ai.data_source.id"

# Span name SHOULD be `{op}` (when the keyed attribute is absent) or
# `{op} {value}` (when present). Mirrors the "SHOULD append when known"
# guidance in semconv.
#
# Avoid `%v ` patterns in sprintf: weaver 0.22.1's OPA-based sprintf
# consumes a single space character immediately following any verb (`%v`,
# `%s`, `%d`) — interpreting it as Go's space-flag — so `%v %v` produces
# `<a><b>` instead of `<a> <b>`. We use `concat` for the literal-space
# joins below.
deny contains _span_finding(
	"genai_span_name_format",
	"violation",
	input.sample.span,
	{
		"operation":     op,
		"keyed_attr":    keyed_attr,
		"expected_form": concat("", [op, " or '", op, " <", keyed_attr, ">'"]),
	},
	concat("", [
		op, " span name should be '",
		op, "' or '",
		op, " <value of ", keyed_attr, ">', got '",
		input.sample.span.name, "'",
	]),
) if {
	input.sample.span
	not _is_mcp_span(input.sample.span)
	op := _attr_value(input.sample.span, "gen_ai.operation.name")
	keyed_attr := _span_name_keyed_attr[op]
	not _valid_op_and_attr_span_name(input.sample.span, op, keyed_attr)
}

# ─── Per-operation expected attributes (violation) ──────────────────────────

_matching_span_type(op, _, "gen_ai.inference.client") if {
	op in {"chat", "generate_content", "text_completion"}
}

_matching_span_type(op, kind, span_type) if {
	not op in {"chat", "generate_content", "text_completion"}
	data["coverage-model"].spans[span_type]
	startswith(span_type, sprintf("gen_ai.%v", [op]))
	endswith(span_type, sprintf(".%v", [kind]))
}

# attributes marked as recommended without a note,
# but they are not always available.
_excluded_recommended := {
	"gen_ai.request.temperature",
	"gen_ai.request.max_tokens",
	"gen_ai.request.top_p",
	"gen_ai.request.stop_sequences",
	"gen_ai.request.presence_penalty",
	"gen_ai.request.frequency_penalty",
	"gen_ai.usage.cache_creation.input_tokens",
	"gen_ai.usage.cache_read.input_tokens",
	"gen_ai.tool.description",
}

_level_expected(level, _) if {
	level == "required"
}

_level_expected(level, attr) if {
	level == "recommended"
	not _excluded_recommended[attr]
}

_expected_for_op(op, kind) := expected if {
	data["coverage-model"].spans
	some span_type
	_matching_span_type(op, kind, span_type)
	attrs := data["coverage-model"].spans[span_type].attributes
	expected := { attr |
		some attr, level in attrs
		_level_expected(level, attr)
	}
}

# Per expected attribute, one violation if missing.
deny contains _span_finding(
	"genai_expected_attribute_missing",
	"violation",
	input.sample.span,
	{
		"operation":         op,
		"missing_attribute": attr_name,
	},
	sprintf(
		"Span '%v' (operation '%v') is missing expected attribute '%v'",
		[input.sample.span.name, op, attr_name],
	),
) if {
	input.sample.span
	not _is_mcp_span(input.sample.span)
	op := _attr_value(input.sample.span, "gen_ai.operation.name")
	expected := _expected_for_op(op, input.sample.span.kind)
	some attr_name in expected
	not _has_attr(input.sample.span, attr_name)
}

# ─── Per-operation span kind (violation) ────────────────────────────────────
#
# Semconv pins the span kind for each operation. `_expected_kinds_for_op`
# returns the set of kinds semconv allows; a span whose kind is outside that
# set is flagged. Single-element sets are the unambiguous cases (inference and
# embeddings are remote calls → CLIENT; tool execution runs in-process →
# INTERNAL). `invoke_agent` / `create_agent` may be same-process or remote, so
# both kinds are allowed. Undefined (→ no violation) for unmapped ops.
_op_allowed_kind(op, span_type, span_def) := kind if {
	startswith(span_type, sprintf("gen_ai.%v", [op]))
	kind := span_def.kind
}

_op_allowed_kind(op, span_type, span_def) := kind if {
	op in {"chat", "generate_content", "text_completion"}
	span_type == "gen_ai.inference.client"
	kind := span_def.kind
}

_expected_kinds_for_op[op] := kinds if {
	some op in _known_operation_names
	kinds := { kind |
		some span_type, span_def in data["coverage-model"].spans
		kind := _op_allowed_kind(op, span_type, span_def)
	}
	count(kinds) > 0
}

deny contains _span_finding(
	"genai_span_kind_unexpected",
	"violation",
	input.sample.span,
	{
		"operation": op,
		"kind":      input.sample.span.kind,
	},
	sprintf(
		"Span '%v' (operation '%v') has kind '%v'; semconv expects one of %v",
		[input.sample.span.name, op, input.sample.span.kind, expected_list],
	),
) if {
	input.sample.span
	not _is_mcp_span(input.sample.span)
	op := _attr_value(input.sample.span, "gen_ai.operation.name")
	expected_kinds := _expected_kinds_for_op[op]
	not expected_kinds[input.sample.span.kind]

	# Sorted in the body, not inline in the head: a comprehension in the head
	# can't see a variable the body binds, and rego reports that only when the
	# rule actually fires — so a kind mismatch aborted the whole advisor run
	# instead of producing this finding.
	expected_list := sort([kind | some kind in expected_kinds])
}

# ─── Unknown gen_ai.operation.name (violation) ──────────────────────────────
#
# Weaver's built-in `undefined_enum_variant` advice is `information`-level;
# we raise unknown values on `gen_ai.operation.name` to a violation.

_known_operation_names[op] if {
	some op in data["coverage-model"].enums["gen_ai.operation.name"]
}

deny contains _span_finding(
	"genai_operation_name_unknown",
	"violation",
	input.sample.span,
	{"operation": op},
	sprintf(
		"Span '%v' has gen_ai.operation.name='%v' which is not a documented enum value",
		[input.sample.span.name, op],
	),
) if {
	input.sample.span
	op := _attr_value(input.sample.span, "gen_ai.operation.name")
	not _known_operation_names[op]
}

# ─── Helpers ────────────────────────────────────────────────────────────────

# Span attributes arrive as `[{"name": ..., "value": ..., "type": ...}]`.

# MCP spans can carry GenAI compatibility attributes for tool calls, but their
# shape and name are governed by the MCP span conventions.
_mcp_span_type["client"] := "mcp.client"
_mcp_span_type["server"] := "mcp.server"

_is_mcp_span(span) if {
	_has_attr(span, "mcp.method.name")
	span_type := _mcp_span_type[span.kind]
	data["coverage-model"].spans[span_type]
}

# True when the span has an attribute named `name`.
_has_attr(span, name) if {
	some attr in span.attributes
	attr.name == name
}

# Returns the value of the named attribute. Undefined (rule body fails) when
# the attribute isn't present — callers must guard with `_has_attr` first if
# they need to distinguish "absent" from "set to a falsy value".
_attr_value(span, name) := value if {
	some attr in span.attributes
	attr.name == name
	value := attr.value
}

# A valid span name is either exactly `{op}` (when the keyed attribute is
# absent) or `{op} {value}` (when present).
_valid_op_and_attr_span_name(span, op, attr_key) if {
	span.name == op
	not _has_attr(span, attr_key)
}

_valid_op_and_attr_span_name(span, op, attr_key) if {
	value := _attr_value(span, attr_key)
	# concat takes strings only and *raises* on anything else, which aborts the
	# whole advisor run rather than producing one finding. A keyed attribute
	# holding a non-string is already wrong; leave saying so to the registry's
	# own type check instead of trying to build a span name out of it.
	is_string(value)
	# concat (not sprintf): see the note above the deny rule. sprintf("%v %v", ...)
	# silently produces "<a><b>" with no space, so every span with a `{op} {value}`
	# name would be reported as a violation.
	span.name == concat(" ", [op, value])
}

# PolicyFinding format per
# https://github.com/open-telemetry/weaver/blob/main/crates/weaver_live_check/README.md#policyfinding
_span_finding(id, level, span, context, message) := {
	"id":          id,
	"level":       level,
	"signal_type": "span",
	"signal_name": span.name,
	"context":     context,
	"message":     message,
}
