"""Mistral-compatible endpoints (chat completions, FIM and embeddings).

Mounted under ``/mistral``, the prefix the agents blueprint already uses:
Mistral serves chat completions at the same ``/v1/chat/completions`` path as
OpenAI, and one path cannot answer as two providers. A scenario points the
SDK's ``server_url`` at the prefixed base URL.
"""

import copy
import json

from flask import Blueprint, Response, request

from ._common import mock_json_schema_value, mock_tool_arguments, sse

bp = Blueprint("mistral", __name__, url_prefix="/mistral")

CHAT_RESPONSE = {
    "id": "mistral-mock-001",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "mistral-small-latest",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a response from the mock server.",
                "tool_calls": None,
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 12,
        "total_tokens": 37,
    },
}

# Mistral validates a tool call id as exactly nine alphanumeric characters,
# and rejects the result message that carries it back otherwise.
TOOL_CALL_ID = "call_mock"


def _tool_call_response(body):
    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["id"] = "mistral-mock-002"
    resp["model"] = body.get("model", resp["model"])
    tool = body.get("tools", [{}])[0]
    function = tool.get("function", tool)
    choice = resp["choices"][0]
    choice["message"]["content"] = ""
    choice["message"]["tool_calls"] = [
        {
            "id": TOOL_CALL_ID,
            "type": "function",
            "index": 0,
            "function": {
                "name": function.get("name") or "get_weather",
                "arguments": json.dumps(mock_tool_arguments(tool)),
            },
        }
    ]
    choice["finish_reason"] = "tool_calls"
    resp["usage"] = {
        "prompt_tokens": 50,
        "completion_tokens": 20,
        "total_tokens": 70,
    }
    return resp


def _structured_content(response_format):
    """The answer a ``json_schema`` request asks for, built from its schema."""
    schema = (response_format.get("json_schema") or {}).get("schema")
    if not schema:
        return None
    return json.dumps(mock_json_schema_value(schema))


def _wants_tool_call(body):
    if not body.get("tools"):
        return False
    return not any(
        message.get("role") == "tool" for message in body.get("messages", [])
    )


def _chat_response(body):
    if _wants_tool_call(body):
        return _tool_call_response(body)

    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        content = _structured_content(response_format)
        if content is not None:
            resp["choices"][0]["message"]["content"] = content
    return resp


def _stream(resp):
    """Yield the SSE chunks of a streamed chat completion.

    The finished response is streamed a piece at a time rather than composed
    separately, so the two routes cannot drift apart: same request, same
    content, whichever way it was asked for.
    """
    message = resp["choices"][0]["message"]
    base = {
        "id": resp["id"],
        "object": "chat.completion.chunk",
        "created": resp["created"],
        "model": resp["model"],
    }

    yield sse(
        {
            **base,
            "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
            ],
        }
    )

    if message.get("tool_calls"):
        yield sse(
            {
                **base,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": message["tool_calls"]},
                        "finish_reason": None,
                    }
                ],
            }
        )
    else:
        for word in (message["content"] or "").split(" "):
            yield sse(
                {
                    **base,
                    "choices": [
                        {"index": 0, "delta": {"content": f"{word} "}, "finish_reason": None}
                    ],
                }
            )

    yield sse(
        {
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": resp["choices"][0]["finish_reason"],
                }
            ],
            "usage": resp["usage"],
        }
    )

    yield "data: [DONE]\n\n"


@bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json(silent=True) or {}
    resp = _chat_response(body)
    if body.get("stream"):
        return Response(_stream(resp), mimetype="text/event-stream")
    return resp


@bp.route("/v1/fim/completions", methods=["POST"])
def fim_completions():
    body = request.get_json(silent=True) or {}
    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["id"] = "mistral-mock-fim-001"
    resp["model"] = body.get("model", "codestral-latest")
    resp["choices"][0]["message"]["content"] = "    return a + b\n"
    return resp


@bp.route("/v1/embeddings", methods=["POST"])
def embeddings():
    body = request.get_json(silent=True) or {}
    raw_input = body.get("inputs", body.get("input"))
    inputs = raw_input if isinstance(raw_input, list) else [raw_input]
    width = int(body.get("output_dimension") or 256)
    return {
        "id": "mistral-mock-embed-001",
        "object": "list",
        "model": body.get("model", "mistral-embed"),
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": [0.001] * max(1, width),
            }
            for index in range(len(inputs))
        ],
        "usage": {
            "prompt_tokens": 8 * len(inputs),
            "total_tokens": 8 * len(inputs),
        },
    }
