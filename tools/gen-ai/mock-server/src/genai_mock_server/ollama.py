"""Ollama-compatible endpoints (chat and embeddings).

Ollama has a wire protocol of its own rather than an OpenAI-compatible one:
a streamed response is newline-delimited JSON rather than SSE, streaming is
the default rather than something a request opts into, tool call arguments
arrive as an object rather than a JSON string, and the answer's shape a
structured request asks for is the ``format`` field itself.
"""

import copy
import json

from flask import Blueprint, Response, request

from ._common import mock_json_schema_value, mock_tool_arguments

bp = Blueprint("ollama", __name__)

CHAT_RESPONSE = {
    "model": "llama3.2",
    "created_at": "2023-11-14T22:13:20Z",
    "message": {
        "role": "assistant",
        "content": "This is a response from the mock server.",
    },
    "done_reason": "stop",
    "done": True,
    "total_duration": 1000000000,
    "load_duration": 100000000,
    "prompt_eval_count": 25,
    "prompt_eval_duration": 200000000,
    "eval_count": 12,
    "eval_duration": 700000000,
}


def _wants_tool_call(body):
    if not body.get("tools"):
        return False
    return not any(
        message.get("role") == "tool" for message in body.get("messages", [])
    )


def _tool_call_response(body):
    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    tool = body.get("tools", [{}])[0]
    function = tool.get("function", tool)
    resp["message"]["content"] = ""
    # Ollama carries the arguments as an object, not as a JSON string.
    resp["message"]["tool_calls"] = [
        {
            "function": {
                "name": function.get("name") or "get_weather",
                "arguments": mock_tool_arguments(tool),
            }
        }
    ]
    resp["prompt_eval_count"] = 50
    resp["eval_count"] = 20
    return resp


def _chat_response(body):
    if _wants_tool_call(body):
        return _tool_call_response(body)

    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    # `format` is the schema itself, so the answer is built from it.
    schema = body.get("format")
    if isinstance(schema, dict):
        resp["message"]["content"] = json.dumps(mock_json_schema_value(schema))
    return resp


def _stream(resp):
    """Yield the NDJSON lines of a streamed chat.

    The finished response is streamed a piece at a time rather than composed
    separately, so the two routes cannot drift apart: same request, same
    content, whichever way it was asked for.
    """
    message = resp["message"]
    base = {"model": resp["model"], "created_at": resp["created_at"]}

    if message.get("tool_calls"):
        yield json.dumps(
            {
                **base,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": message["tool_calls"],
                },
                "done": False,
            }
        ) + "\n"
    else:
        for word in (message["content"] or "").split(" "):
            yield json.dumps(
                {
                    **base,
                    "message": {"role": "assistant", "content": f"{word} "},
                    "done": False,
                }
            ) + "\n"

    final = {key: value for key, value in resp.items() if key != "message"}
    yield json.dumps({**final, "message": {"role": "assistant", "content": ""}}) + "\n"


@bp.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    resp = _chat_response(body)
    # Ollama streams unless it is told not to, so an omitted field means yes.
    if body.get("stream", True):
        return Response(_stream(resp), mimetype="application/x-ndjson")
    return resp


@bp.route("/api/embed", methods=["POST"])
def embed():
    body = request.get_json(silent=True) or {}
    raw_input = body.get("input")
    inputs = raw_input if isinstance(raw_input, list) else [raw_input]
    width = int(body.get("dimensions") or 256)
    return {
        "model": body.get("model", "nomic-embed-text"),
        "embeddings": [[0.001] * max(1, width) for _ in inputs],
        "total_duration": 1000000000,
        "load_duration": 100000000,
        "prompt_eval_count": 8 * len(inputs),
    }
