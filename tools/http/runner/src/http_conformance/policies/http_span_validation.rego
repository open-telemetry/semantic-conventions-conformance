# HTTP span shape, beyond what weaver checks on its own.
#
# Two things the registry can't give us:
#
#   1. Which attributes an HTTP span must carry. Weaver validates each
#      attribute it *sees* against the registry, but doesn't match a span to a
#      span definition, so it never reports one as missing. The manifests
#      below are the registry's `required` levels, plus the subset of
#      `recommended` that is unconditional.
#
#   2. The span name, which isn't an attribute at all. It matters more here
#      than almost anywhere: a span named after the request *path* rather than
#      the route template makes every request a new span name.
#
# Span status and `error.type` are checked by the runner's own policies,
# loaded alongside this file.
#
# https://opentelemetry.io/docs/specs/semconv/http/http-spans/

package live_check_advice

import rego.v1

# ─── Expected attributes ────────────────────────────────────────────────────
#
# Sourced from the registry's own requirement levels — see
# `http_conformance.classify_span` for the same two span types in Python.

_http_required["server"] := {
	"http.request.method",
	"url.path",
	"url.scheme",
}

_http_required["client"] := {
	"http.request.method",
	"server.address",
	"server.port",
	"url.full",
}

# Only the Recommended attributes an instrumentation can always set. The rest
# of that level is conditional in prose the registry flattens away —
# `http.request.resend_count` exists only on a retry, `network.peer.*` only
# when the peer differs from the logical server, `user_agent.original` only
# when the client sent the header — and flagging those would blame the
# instrumentation for the request it was given.
_http_recommended["server"] := {
	"client.address",
	"network.protocol.version",
	"server.address",
}

_http_recommended["client"] := {"network.protocol.version"}

deny contains _http_span_finding(
	"required_attribute_not_present",
	"violation",
	input.sample.span,
	{"attribute_key": attr_name, "kind": kind},
	sprintf(
		"Span '%v' is missing required attribute '%v'",
		[input.sample.span.name, attr_name],
	),
) if {
	kind := _http_span_kind(input.sample.span)
	some attr_name in _http_required[kind]
	not _http_has_attr(input.sample.span, attr_name)
}

deny contains _http_span_finding(
	"recommended_attribute_not_present",
	"violation",
	input.sample.span,
	{"attribute_key": attr_name, "kind": kind},
	sprintf(
		"Span '%v' is missing recommended attribute '%v'",
		[input.sample.span.name, attr_name],
	),
) if {
	kind := _http_span_kind(input.sample.span)
	some attr_name in _http_recommended[kind]
	not _http_has_attr(input.sample.span, attr_name)
}

# ─── Span name ──────────────────────────────────────────────────────────────

# The name semconv gives a request whose method the instrumentation doesn't
# recognise. Its span is named "HTTP" with no method appended.
_http_other_method_name := "HTTP"

# Server: `{method} {http.route}`, or `{method}` when there is no route —
# a request that matched no handler has no low-cardinality template to use.
_http_expected_names(span, "server") := names if {
	method := _http_attr_value(span, "http.request.method")
	names := _http_names_with(method, _http_route(span))
}

# Client: `{method}`, or `{method} {url.template}` when the instrumentation
# knows the template. Never the URL — that is unbounded cardinality.
_http_expected_names(span, "client") := names if {
	method := _http_attr_value(span, "http.request.method")
	names := _http_names_with(method, _http_template(span))
}

# `{method}` is the literal "HTTP" for a method the instrumentation doesn't
# recognise; the `{method} {target}` form still applies on top of it.
_http_names_with(method, suffixes) := _http_names_from(_http_other_method_name, suffixes) if {
	method == "_OTHER"
}

_http_names_with(method, suffixes) := _http_names_from(method, suffixes) if {
	method != "_OTHER"
	# concat raises on a non-string, which aborts the whole advisor run rather
	# than producing one finding. A method holding a non-string is already
	# wrong; leave saying so to the registry's own type check.
	is_string(method)
}

_http_names_from(method, suffixes) := {method} | {
	concat(" ", [method, suffix]) |
	some suffix in suffixes
}

# A set so the rule stays quiet when the attribute is absent or not a string.
_http_route(span) := {route |
	route := _http_attr_value(span, "http.route")
	is_string(route)
}

_http_template(span) := {template |
	template := _http_attr_value(span, "url.template")
	is_string(template)
}

deny contains _http_span_finding(
	"http_span_name_format",
	"violation",
	input.sample.span,
	{
		"kind":     kind,
		"expected": expected_list,
	},
	sprintf(
		"Span '%v' should be named one of %v; a name built from the request path or URL makes every request a new span name.",
		[input.sample.span.name, expected_list],
	),
) if {
	kind := _http_span_kind(input.sample.span)
	expected := _http_expected_names(input.sample.span, kind)
	not expected[input.sample.span.name]

	# Sorted in the body, not inline in the head: a comprehension in the head
	# can't see a variable the body binds, and rego reports that only when the
	# rule actually fires — so a misnamed span would abort the whole advisor
	# run instead of producing this finding.
	expected_list := sort([name | some name in expected])
}

# ─── Helpers ────────────────────────────────────────────────────────────────
#
# Prefixed `_http_`: every policy file weaver loads lands in one package, so a
# helper named the same as the runner's or another domain's would collide.

# An HTTP span, by its kind. Undefined — so no rule above fires — for a span
# that isn't HTTP, and for one whose kind the conventions don't allow, which
# weaver reports on its own.
# Normalised the same way `http_conformance.classify_span` normalises it.
# Weaver's own ingest rejects any other spelling, so this only ever lowercases
# something already lowercase — but the two sides deciding "is this an HTTP
# span" differently is the kind of drift that makes a check vanish quietly.
_http_span_kind(span) := kind if {
	span
	_http_has_attr(span, "http.request.method")
	kind := trim_prefix(lower(span.kind), "span_kind_")
	kind in {"client", "server"}
}

_http_has_attr(span, name) if {
	some attr in span.attributes
	attr.name == name
}

_http_attr_value(span, name) := value if {
	some attr in span.attributes
	attr.name == name
	value := attr.value
}

_http_span_finding(id, level, span, context, message) := {
	"id":          id,
	"level":       level,
	"signal_type": "span",
	"signal_name": span.name,
	"context":     context,
	"message":     message,
}
