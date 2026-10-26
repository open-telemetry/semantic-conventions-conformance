"""Shared helpers for mock server provider modules."""

import binascii
import json
import struct


def sse(obj):
    """Format an OpenAI-style SSE ``data:`` line."""
    return f"data: {json.dumps(obj)}\n\n"


def mock_tool_argument_value(name, schema):
    schema_type = (schema or {}).get("type")
    if name == "location":
        return "Seattle"
    if name == "message":
        return "This is a response from the mock server."
    if schema_type == "string":
        return f"mock-{name}"
    if schema_type in {"integer", "number"}:
        return 1
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    return f"mock-{name}"


# A client parses these back into a typed value, so "mock-<name>" would fail.
_MOCK_STRING_FORMATS = {
    "date-time": "2023-11-14T22:13:20Z",
    "date": "2023-11-14",
    "time": "22:13:20",
    "uuid": "00000000-0000-4000-8000-000000000000",
    "email": "mock@example.com",
    "uri": "https://example.com/mock",
}


def _resolve(schema, root):
    """Follow a local ``$ref`` to the fragment it names.

    Any schema generated from a class rather than written by hand puts nested
    types in ``$defs`` and refers to them, so a generator that does not follow
    the reference answers a nested object with a string.
    """
    seen = set()
    while isinstance(schema, dict) and "$ref" in schema:
        reference = schema["$ref"]
        if reference in seen or not reference.startswith("#/"):
            return {}
        seen.add(reference)
        target = root
        for step in reference[2:].split("/"):
            if not isinstance(target, dict) or step not in target:
                return {}
            target = target[step]
        schema = target
    return schema or {}


def _first_usable(alternatives, root):
    """The first branch of an anyOf/oneOf that is not the null of an optional."""
    for alternative in alternatives:
        resolved = _resolve(alternative, root)
        if resolved.get("type") != "null":
            return resolved
    return {}


def mock_json_schema_value(schema, name="value", root=None, depth=0):
    """Build a deterministic value satisfying a JSON Schema fragment.

    Structured-output requests carry the schema the answer has to match, so the
    answer is generated from it rather than from a fixed payload: any scenario's
    schema is served without adding a branch here.
    """
    root = schema if root is None else root
    schema = _resolve(schema, root)
    # A model that refers to itself has no finite answer.
    if depth > 8:
        return {}

    for keyword in ("anyOf", "oneOf"):
        alternatives = schema.get(keyword)
        if alternatives:
            return mock_json_schema_value(
                _first_usable(alternatives, root), name, root, depth + 1
            )
    if schema.get("allOf"):
        # An intersection: every branch applies at once, on top of whatever the
        # schema declares alongside them. Nothing here forces a type.
        merged = {k: v for k, v in schema.items() if k != "allOf"}
        properties = dict(merged.get("properties") or {})
        for alternative in schema["allOf"]:
            resolved = _resolve(alternative, root)
            properties.update(resolved.get("properties") or {})
            for keyword, value in resolved.items():
                if keyword not in ("properties", "$ref"):
                    merged.setdefault(keyword, value)
        if properties:
            merged["properties"] = properties
        schema = merged

    if "const" in schema:
        return schema["const"]
    if schema.get("enum"):
        return schema["enum"][0]

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        # A nullable field is described as ["string", "null"]; answer with the
        # value rather than the null so the field carries something.
        schema_type = next(
            (entry for entry in schema_type if entry != "null"), "string"
        )

    if schema_type == "object":
        properties = schema.get("properties", {})
        # Every property, not just the required ones: otherwise the answer
        # depends on which fields the caller happened to mark.
        return {
            key: mock_json_schema_value(subschema, key, root, depth + 1)
            for key, subschema in properties.items()
        }
    if schema_type == "array":
        return [
            mock_json_schema_value(schema.get("items", {}), name, root, depth + 1)
        ]
    if schema_type == "string" and schema.get("format") in _MOCK_STRING_FORMATS:
        return _MOCK_STRING_FORMATS[schema["format"]]
    return mock_tool_argument_value(name, {"type": schema_type or "string"})


def current_turn(messages):
    """Messages since the last user message.

    A tool called in an earlier turn must not stop the model from calling it
    again when the user asks a new question.
    """
    last_user = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            last_user = index
    return messages[last_user + 1 :]


def called_tool_info(messages):
    """Tool names called, and every tool call id seen, in OpenAI chat shape."""
    called_names = set()
    call_ids = []
    for message in messages:
        for call in message.get("tool_calls") or []:
            call_id = call.get("id")
            if call_id:
                call_ids.append(call_id)
            name = (call.get("function") or {}).get("name")
            if name:
                called_names.add(name)
        if message.get("role") == "tool":
            call_id = message.get("tool_call_id")
            if call_id:
                call_ids.append(call_id)
    return called_names, call_ids


def offered_tool(body):
    """The first tool a request offers, and its name."""
    tools = body.get("tools") or []
    if not tools:
        return None, None
    tool = tools[0]
    function = tool.get("function", tool)
    return tool, function.get("name") or tool.get("name")


def should_call_tool(body):
    """Whether to answer this request with a call to its first offered tool.

    True while the current turn holds no result for that tool. Scoping to the
    turn rather than the whole history is what lets a conversation call the
    same tool again after the user asks a second question.
    """
    tool, tool_name = offered_tool(body)
    if not tool or not tool_name:
        return False
    turn = current_turn(body.get("messages", []))
    if not any(message.get("role") == "tool" for message in turn):
        return True
    called_names, _ = called_tool_info(turn)
    # A result with no call to attribute it to: answer rather than loop.
    return bool(called_names) and tool_name not in called_names


def next_tool_call_index(messages):
    """1-based number of the next tool call, past the ids already in play.

    Agent handoffs replay earlier turns, so a fixed id would repeat across
    calls the framework expects to tell apart.
    """
    _, call_ids = called_tool_info(messages)
    return len(set(call_ids)) + 1


def mock_tool_arguments(tool):
    function = (tool or {}).get("function", {})
    parameters = function.get("parameters") or (tool or {}).get("parameters") or (tool or {}).get("input_schema", {})
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    argument_names = list(required) or list(properties)
    if not argument_names:
        return {"value": "mock-value"}

    return {
        name: mock_json_schema_value(
            properties.get(name, {}), name, root=parameters
        )
        for name in argument_names
    }


def encode_aws_event_stream_message(event_type, payload_bytes):
    """Encode a single AWS event-stream binary message.

    Format (all big-endian):
      total_length (4) | headers_length (4) | prelude_crc (4)
      headers (variable) | payload (variable) | message_crc (4)
    """

    def _crc32(data):
        return binascii.crc32(data) & 0xFFFFFFFF

    def _encode_header(name, value):
        name_bytes = name.encode("utf-8")
        value_bytes = value.encode("utf-8")
        # 1 byte name len + name + 1 byte type (7=string) + 2 bytes value len + value
        return (
            struct.pack("!B", len(name_bytes))
            + name_bytes
            + struct.pack("!B", 7)
            + struct.pack("!H", len(value_bytes))
            + value_bytes
        )

    headers = b""
    headers += _encode_header(":message-type", "event")
    headers += _encode_header(":event-type", event_type)
    headers += _encode_header(":content-type", "application/json")

    total_length = 4 + 4 + 4 + len(headers) + len(payload_bytes) + 4
    prelude = struct.pack("!II", total_length, len(headers))
    prelude_crc = struct.pack("!I", _crc32(prelude))
    message_no_crc = prelude + prelude_crc + headers + payload_bytes
    message_crc = struct.pack("!I", _crc32(message_no_crc))
    return message_no_crc + message_crc
