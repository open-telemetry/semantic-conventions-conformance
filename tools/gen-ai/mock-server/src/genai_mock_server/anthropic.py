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

    A tool called in an earlier turn must not stop the model from calling it
    again when the user asks a new question.
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


def _has_tool_result(body):
    for message in body.get("messages", []):
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                ):
                    return True
    return False


def _get_anthropic_tool_info(messages):
    called_names = set()
    call_ids = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        call_id = block.get("id")
                        if call_id:
                            call_ids.append(call_id)
                        name = block.get("name")
                        if name:
                            called_names.add(name)
                    elif block.get("type") == "tool_result":
                        call_id = block.get("tool_use_id")
                        if call_id:
                            call_ids.append(call_id)
    return called_names, call_ids


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
    if any(
        edit.get("type") == "compact_20260112"
        for edit in edits
        if isinstance(edit, dict)
    ):
        resp = copy.deepcopy(MESSAGE_COMPACTION_RESPONSE)
        resp["model"] = body.get("model", resp["model"])
        return resp

    if body.get("tools"):
        tools = body.get("tools")
        first_tool = tools[0] if tools else {}
        tool_name = first_tool.get("name")
        messages = body.get("messages", [])
        _, call_ids = _get_anthropic_tool_info(messages)
        turn = _current_turn(messages)
        called_names, _ = _get_anthropic_tool_info(turn)
        if not _has_tool_result({"messages": turn}):
            should_call = True
        elif called_names:
            should_call = bool(tool_name) and tool_name not in called_names
        else:
            # A result with no call to attribute it to: answer rather than loop.
            should_call = False

        if should_call:
            call_idx = len(set(call_ids)) + 1
            call_id = f"toolu_mock_{call_idx:03d}"
            resp = copy.deepcopy(MESSAGE_TOOL_USE_RESPONSE)
            resp["model"] = body.get("model", resp["model"])
            if tool_name:
                resp["content"][0]["name"] = tool_name
            resp["content"][0]["id"] = call_id
            resp["content"][0]["input"] = mock_tool_arguments(first_tool)
            return resp

    resp = copy.deepcopy(MESSAGE_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    return resp
