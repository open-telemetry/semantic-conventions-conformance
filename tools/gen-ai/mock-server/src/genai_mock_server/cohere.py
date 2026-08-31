"""Cohere-compatible endpoints."""

import copy
import json

from flask import Blueprint, Response, request

from ._common import mock_json_schema_value, mock_tool_arguments

bp = Blueprint("cohere", __name__)

CHAT_RESPONSE = {
    "id": "cohere-mock-001",
    "finish_reason": "COMPLETE",
    "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": "This is a response from the mock server."}],
    },
    "usage": {
        "billed_units": {"input_tokens": 25, "output_tokens": 12},
        "tokens": {"input_tokens": 25, "output_tokens": 12},
    },
}

TOOL_CALL_ID = "cohere-mock-tool-call-001"


def _wants_tool_call(body):
    if not body.get("tools"):
        return False
    return not any(
        message.get("role") == "tool" for message in body.get("messages", [])
    )


def _tool_call_response(body):
    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["id"] = "cohere-mock-002"
    tool = body.get("tools", [{}])[0]
    function = tool.get("function", tool)
    resp["finish_reason"] = "TOOL_CALL"
    resp["message"] = {
        "role": "assistant",
        # Cohere narrates the call before making it; the field is its own.
        "tool_plan": "I will look up the weather.",
        "tool_calls": [
            {
                "id": TOOL_CALL_ID,
                "type": "function",
                "function": {
                    "name": function.get("name") or "get_weather",
                    "arguments": json.dumps(mock_tool_arguments(tool)),
                },
            }
        ],
    }
    resp["usage"] = {
        "billed_units": {"input_tokens": 50, "output_tokens": 20},
        "tokens": {"input_tokens": 50, "output_tokens": 20},
    }
    return resp


def _chat_response(body):
    if _wants_tool_call(body):
        return _tool_call_response(body)

    resp = copy.deepcopy(CHAT_RESPONSE)
    response_format = body.get("response_format") or {}
    schema = response_format.get("json_schema") or response_format.get("schema")
    if response_format.get("type") == "json_object" and schema:
        resp["message"]["content"][0]["text"] = json.dumps(mock_json_schema_value(schema))
    return resp


def _event(event_type, payload):
    """Format one Cohere v2 streaming event."""
    return f"event: {event_type}\ndata: {json.dumps({'type': event_type, **payload})}\n\n"


def _stream(resp):
    """Yield the events of a streamed v2 chat.

    The finished response is streamed a piece at a time rather than composed
    separately, so the two routes cannot drift apart: same request, same
    content, whichever way it was asked for.
    """
    message = resp["message"]
    yield _event("message-start", {"id": resp["id"], "delta": {"message": {"role": "assistant"}}})

    if message.get("tool_calls"):
        call = message["tool_calls"][0]
        yield _event(
            "tool-plan-delta",
            {"delta": {"message": {"tool_plan": message.get("tool_plan", "")}}},
        )
        yield _event(
            "tool-call-start",
            {
                "index": 0,
                "delta": {
                    "message": {
                        "tool_calls": {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["function"]["name"], "arguments": ""},
                        }
                    }
                },
            },
        )
        yield _event(
            "tool-call-delta",
            {
                "index": 0,
                "delta": {
                    "message": {
                        "tool_calls": {
                            "function": {"arguments": call["function"]["arguments"]}
                        }
                    }
                },
            },
        )
        yield _event("tool-call-end", {"index": 0})
    else:
        yield _event(
            "content-start",
            {"index": 0, "delta": {"message": {"content": {"type": "text", "text": ""}}}},
        )
        for word in message["content"][0]["text"].split(" "):
            yield _event(
                "content-delta",
                {"index": 0, "delta": {"message": {"content": {"text": f"{word} "}}}},
            )
        yield _event("content-end", {"index": 0})

    yield _event(
        "message-end",
        {"delta": {"finish_reason": resp["finish_reason"], "usage": resp["usage"]}},
    )


@bp.route("/v2/chat", methods=["POST"])
def cohere_chat():
    body = request.get_json(silent=True) or {}
    resp = _chat_response(body)
    if body.get("stream"):
        return Response(_stream(resp), mimetype="text/event-stream")
    return resp


@bp.route("/v1/chat", methods=["POST"])
def cohere_chat_v1():
    return {
        "text": "This is a response from the mock server.",
        "generation_id": "cohere-mock-001",
        "finish_reason": "COMPLETE",
        "meta": {
            "tokens": {"input_tokens": 25, "output_tokens": 12},
            "billed_units": {"input_tokens": 25, "output_tokens": 12},
        },
    }


def _embed_response(body, version):
    raw = body.get("texts") or body.get("inputs") or ["Hello, world!"]
    width = int(body.get("output_dimension") or 256)
    vectors = [[0.001] * max(1, width) for _ in raw]
    if version == "2":
        return {
            "id": "cohere-embed-mock-001",
            "embeddings": {"float": vectors},
            "texts": raw,
            "meta": {
                "api_version": {"version": "2"},
                "billed_units": {"input_tokens": 8 * len(raw)},
            },
        }
    return {
        "response_type": "embeddings_floats",
        "id": "cohere-embed-mock-001",
        "embeddings": vectors,
        "texts": raw,
        "meta": {
            "api_version": {"version": "1"},
            "billed_units": {"input_tokens": 8 * len(raw)},
        },
    }


@bp.route("/v2/embed", methods=["POST"])
def cohere_embed():
    return _embed_response(request.get_json(silent=True) or {}, "2")


@bp.route("/v1/embed", methods=["POST"])
def cohere_embed_v1():
    return _embed_response(request.get_json(silent=True) or {}, "1")
