"""AWS Bedrock-compatible endpoints."""

import base64
import copy
import json

from flask import Blueprint, Response, request

from ._common import encode_aws_event_stream_message, mock_tool_arguments

bp = Blueprint("bedrock", __name__)


CONVERSE_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "This is a response from the mock server."}],
        }
    },
    "stopReason": "end_turn",
    "usage": {
        "inputTokens": 25,
        "outputTokens": 12,
        "totalTokens": 37,
    },
    "metrics": {"latencyMs": 100},
}


CONVERSE_TOOL_USE_RESPONSE = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tooluse_mock_001",
                        # Filled from the tool the request offered.
                        "name": None,
                        "input": {},
                    }
                }
            ],
        }
    },
    "stopReason": "tool_use",
    "usage": {
        "inputTokens": 50,
        "outputTokens": 20,
        "totalTokens": 70,
    },
    "metrics": {"latencyMs": 100},
}


def _has_tool_result(body):
    for message in body.get("messages") or []:
        for block in message.get("content") or []:
            if isinstance(block, dict) and "toolResult" in block:
                return True
    return False


def _tool_to_call(body):
    """The tool the response should call, or None when none was offered.

    `toolChoice` names one when the request forces it; otherwise the first
    tool offered is the one called.
    """
    tool_config = body.get("toolConfig") or {}
    specifications = [
        tool["toolSpec"]
        for tool in tool_config.get("tools") or []
        if isinstance(tool, dict) and tool.get("toolSpec", {}).get("name")
    ]
    if not specifications:
        return None
    chosen = ((tool_config.get("toolChoice") or {}).get("tool") or {}).get(
        "name"
    )
    for specification in specifications:
        if specification["name"] == chosen:
            return specification
    return specifications[0]


def _converse_tool_use_response(specification):
    response = copy.deepcopy(CONVERSE_TOOL_USE_RESPONSE)
    tool_use = response["output"]["message"]["content"][0]["toolUse"]
    tool_use["name"] = specification["name"]
    schema = (specification.get("inputSchema") or {}).get("json") or {}
    tool_use["input"] = mock_tool_arguments({"parameters": schema})
    return response


def _stream_converse():
    """Yield Bedrock ConverseStream event-stream chunks in binary format."""
    events = []
    events.append(("messageStart", {"role": "assistant"}))
    for word in ["This ", "is ", "a ", "mock ", "streamed ", "response."]:
        events.append(
            (
                "contentBlockDelta",
                {"delta": {"text": word}, "contentBlockIndex": 0},
            )
        )
    events.append(("contentBlockStop", {"contentBlockIndex": 0}))
    events.append(("messageStop", {"stopReason": "end_turn"}))
    events.append(
        (
            "metadata",
            {
                "usage": {
                    "inputTokens": 25,
                    "outputTokens": 6,
                    "totalTokens": 31,
                },
                "metrics": {"latencyMs": 100},
            },
        )
    )
    for event_type, body in events:
        payload = json.dumps(body).encode("utf-8")
        yield encode_aws_event_stream_message(event_type, payload)


@bp.route("/model/<path:model_id>/converse", methods=["POST"])
def bedrock_converse(model_id):
    body = request.get_json(silent=True) or {}
    if not _has_tool_result(body):
        specification = _tool_to_call(body)
        if specification is not None:
            return _converse_tool_use_response(specification)
    return CONVERSE_RESPONSE


@bp.route("/model/<path:model_id>/converse-stream", methods=["POST"])
def bedrock_converse_stream(model_id):
    return Response(
        _stream_converse(), mimetype="application/vnd.amazon.eventstream"
    )


@bp.route("/model/<path:model_id>/invoke", methods=["POST"])
def bedrock_invoke(model_id):
    """Handle Bedrock InvokeModel."""
    if "embed" in model_id:
        resp = {
            "embedding": [0.001] * 256,
            "inputTextTokenCount": 8,
        }
        headers = {
            "x-amzn-bedrock-input-token-count": "8",
            "x-amzn-bedrock-content-type": "application/json",
        }
        return Response(
            json.dumps(resp), mimetype="application/json", headers=headers
        )

    resp = {
        "inputTextTokenCount": 5,
        "results": [
            {
                "tokenCount": 10,
                "outputText": "This is a response from the mock server.",
                "completionReason": "FINISH",
            }
        ],
    }
    headers = {
        "x-amzn-bedrock-input-token-count": "5",
        "x-amzn-bedrock-output-token-count": "10",
        "x-amzn-bedrock-content-type": "application/json",
    }
    return Response(
        json.dumps(resp), mimetype="application/json", headers=headers
    )


def _stream_invoke():
    """Yield Bedrock InvokeModelWithResponseStream event-stream chunks in binary format."""
    # Titan streams `totalOutputTextTokenCount`, not the `tokenCount` its
    # non-streaming response carries, and only fills it on the final chunk.
    chunks = [
        {
            "outputText": "This is ",
            "index": 0,
            "totalOutputTextTokenCount": None,
            "completionReason": None,
            "inputTextTokenCount": 5,
        },
        {
            "outputText": "a test",
            "index": 0,
            "totalOutputTextTokenCount": 10,
            "completionReason": "FINISH",
            "inputTextTokenCount": 5,
            "amazon-bedrock-invocationMetrics": {
                "inputTokenCount": 5,
                "outputTokenCount": 10,
                "firstByteLatency": 100,
                "invocationLatency": 200,
            },
        },
    ]
    for chunk in chunks:
        raw_bytes = json.dumps(chunk).encode("utf-8")
        payload = json.dumps(
            {"bytes": base64.b64encode(raw_bytes).decode("ascii")}
        ).encode("utf-8")
        yield encode_aws_event_stream_message("chunk", payload)


@bp.route(
    "/model/<path:model_id>/invoke-with-response-stream", methods=["POST"]
)
def bedrock_invoke_stream(model_id):
    """Handle Bedrock InvokeModelWithResponseStream."""
    headers = {
        "x-amzn-bedrock-content-type": "application/json",
    }
    return Response(
        _stream_invoke(),
        mimetype="application/vnd.amazon.eventstream",
        headers=headers,
    )
