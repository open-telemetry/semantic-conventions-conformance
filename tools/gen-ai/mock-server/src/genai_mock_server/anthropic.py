"""Anthropic-compatible messages endpoint."""

import copy
import json

from flask import Blueprint, Response, request

from ._common import mock_tool_arguments

bp = Blueprint("anthropic", __name__)


MESSAGE_RESPONSE = {
    "id": "msg-mock-001",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": "This is a response from the mock server.",
        }
    ],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {
        "input_tokens": 25,
        "output_tokens": 12,
        "cache_creation_input_tokens": 5,
        "cache_read_input_tokens": 3,
    },
}

MESSAGE_TOOL_USE_RESPONSE = {
    "id": "msg-mock-002",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_mock_001",
            "name": "get_weather",
            "input": {"location": "Seattle"},
        }
    ],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "tool_use",
    "stop_sequence": None,
    "usage": {
        "input_tokens": 50,
        "output_tokens": 20,
    },
}


MESSAGE_COMPACTION_RESPONSE = {
    "id": "msg-mock-compaction-001",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "compaction",
            "encrypted_content": "opaque encrypted compaction state",
        }
    ],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "compaction",
    "stop_sequence": None,
    "usage": {
        "input_tokens": 25,
        "output_tokens": 8,
        "iterations": [
            {
                "type": "compaction",
                "input_tokens": 80,
                "output_tokens": 8,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        ],
    },
}


def _current_turn(messages):
    """Messages since the last user message that is not a tool result.

    Anthropic carries tool results as user messages, so a plain split on the
    last user message would put every turn's result in its own turn.
    """
    last_user = -1
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        ):
            continue
        last_user = index
    return messages[last_user + 1 :]


def _called_tool_info(messages):
    """Tool names called, and every tool id seen, in Anthropic block shape."""
    called_names = set()
    call_ids = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                if block.get("id"):
                    call_ids.append(block["id"])
                if block.get("name"):
                    called_names.add(block["name"])
            elif block.get("type") == "tool_result":
                if block.get("tool_use_id"):
                    call_ids.append(block["tool_use_id"])
    return called_names, call_ids


def _should_call_tool(messages, tool_name):
    """Whether this turn still needs a call to ``tool_name``.

    Scoped to the turn so a completed call does not exhaust the tool for the
    rest of the conversation.
    """
    if not tool_name:
        return False
    turn = _current_turn(messages)
    if not _has_tool_result({"messages": turn}):
        return True
    called_names, _ = _called_tool_info(turn)
    # A result with no call to attribute it to: answer rather than loop.
    return bool(called_names) and tool_name not in called_names


def _has_tool_result(body):
    for message in body.get("messages", []):
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    return True
    return False


def _sse_event(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _stream_message(body):
    """Yield SSE events for Anthropic streaming."""
    model = body.get("model", "claude-sonnet-4-20250514")

    yield _sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": "msg-mock-stream-001",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 25, "output_tokens": 0},
            },
        },
    )

    yield _sse_event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
    )

    for word in ["This ", "is ", "a ", "mock ", "streamed ", "response."]:
        yield _sse_event(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": word},
            },
        )

    yield _sse_event(
        "content_block_stop",
        {
            "type": "content_block_stop",
            "index": 0,
        },
    )

    yield _sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 6},
        },
    )

    yield _sse_event(
        "message_stop",
        {
            "type": "message_stop",
        },
    )


@bp.route("/v1/messages", methods=["POST"])
def messages():
    body = request.get_json(silent=True) or {}

    if body.get("stream"):
        return Response(_stream_message(body), mimetype="text/event-stream")

    context_management = body.get("context_management") or {}
    edits = context_management.get("edits") or []
    if any(edit.get("type") == "compact_20260112" for edit in edits if isinstance(edit, dict)):
        resp = copy.deepcopy(MESSAGE_COMPACTION_RESPONSE)
        resp["model"] = body.get("model", resp["model"])
        return resp

    messages = body.get("messages", [])
    tool = (body.get("tools") or [{}])[0]
    tool_name = tool.get("name")
    if body.get("tools") and _should_call_tool(messages, tool_name):
        _, call_ids = _called_tool_info(messages)
        resp = copy.deepcopy(MESSAGE_TOOL_USE_RESPONSE)
        resp["model"] = body.get("model", resp["model"])
        resp["content"][0]["id"] = f"toolu_mock_{len(set(call_ids)) + 1:03d}"
        resp["content"][0]["name"] = tool_name
        resp["content"][0]["input"] = mock_tool_arguments(tool)
        return resp

    resp = copy.deepcopy(MESSAGE_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    return resp
