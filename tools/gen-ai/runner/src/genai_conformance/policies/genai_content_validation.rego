# Validates the JSON payload of GenAI content attributes against the semconv
# JSON schemas. The schemas ship with the semconv-genai registry
# (model/gen-ai/*.json) and are loaded into rego data by weaver's `--advice-data`
# flag, keyed by the schema file's stem (e.g. gen-ai-input-messages.json ->
# data["gen-ai-input-messages"]), so this policy references them as data
# documents rather than inlining them.

package live_check_advice

import rego.v1

# Content attribute name -> advice-data key (the schema file's stem).
_genai_content_schema_keys := {
	"gen_ai.input.messages":      "gen-ai-input-messages",
	"gen_ai.output.messages":     "gen-ai-output-messages",
	"gen_ai.system_instructions": "gen-ai-system-instructions",
	"gen_ai.tool.definitions":    "gen-ai-tool-definitions",
	"gen_ai.retrieval.documents": "gen-ai-retrieval-documents",
}

# The sample under check, when it is a content attribute with a schema to check
# it against. Undefined (so every rule below skips the sample) when the schema
# isn't loaded for the pinned semconv version yet — e.g. forward-looking
# attributes like `gen_ai.tool.definitions` before upstream ships the schema.
_content_sample := {"name": attr_name, "value": attr_value, "schema": data[key]} if {
	input.sample.attribute
	attr_name := input.sample.attribute.name
	attr_value := input.sample.attribute.value
	is_string(attr_value)

	key := _genai_content_schema_keys[attr_name]
	data[key]
}

deny contains _content_finding(
	sample.name,
	errors,
	sprintf(
		"Attribute '%v' value does not conform to the GenAI schema: %v",
		[sample.name, errors],
	),
) if {
	sample := _content_sample
	json.is_valid(sample.value)
	parsed := json.unmarshal(sample.value)

	[matched, errors] := json.match_schema(parsed, sample.schema)
	not matched
}

# An implementation that puts something other than JSON in a content attribute
# fails the same check, one step earlier: the schema cannot be applied to a
# value that never parsed.
deny contains _content_finding(
	sample.name,
	"value is not JSON",
	sprintf(
		"Attribute '%v' value is not JSON, so it cannot carry the GenAI content schema",
		[sample.name],
	),
) if {
	sample := _content_sample
	not json.is_valid(sample.value)
}

# PolicyFinding format per
# https://github.com/open-telemetry/weaver/blob/main/crates/weaver_live_check/README.md#policyfinding
# (id / level / context / message). `signal_type` and `signal_name` are left to
# weaver, which stamps the signal the sample came from — for an attribute-level
# sample that is the span or event holding it, which is what a reader of the
# finding needs and what this rule cannot see.
_content_finding(attr_name, errors, message) := {
	"id":    "genai_content_schema",
	"level": "violation",
	"context": {
		"attribute": attr_name,
		"errors":    errors,
	},
	"message": message,
}
