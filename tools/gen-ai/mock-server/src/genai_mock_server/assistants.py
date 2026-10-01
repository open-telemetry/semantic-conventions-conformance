"""OpenAI Assistants / Azure AI Foundry Agents -compatible endpoints."""

import json

from flask import Blueprint, request

from ._common import mock_tool_arguments

bp = Blueprint("assistants", __name__)


# Shared state for mock Assistants resources.
_assistants: dict[str, dict] = {}
_runs: dict[str, dict] = {}


@bp.route("/agents/<agent_name>/versions", methods=["POST"])
def create_agent_version(agent_name):
    body = request.get_json(silent=True) or {}
    definition = body.get("definition", {})
    return {
        "object": "agent.version",
        "id": "agent-version-mock-001",
        "name": agent_name,
        "version": "1",
        "description": body.get("description"),
        "created_at": "2026-04-08T00:00:00Z",
        "metadata": body.get("metadata", {}),
        "definition": definition,
    }


@bp.route("/agents/<agent_name>/versions/<agent_version>", methods=["DELETE"])
def delete_agent_version(agent_name, agent_version):
    return {
        "object": "agent.version.deleted",
        "name": agent_name,
        "version": agent_version,
        "deleted": True,
    }


@bp.route("/v1/assistants", methods=["POST"])
@bp.route("/openai/assistants", methods=["POST"])
@bp.route("/assistants", methods=["POST"])
def create_assistant():
    body = request.get_json(silent=True) or {}
    assistant = {
        "id": "asst-mock-001",
        "object": "assistant",
        "created_at": 1700000000,
        "name": body.get("name", "mock-assistant"),
        "description": body.get("description"),
        "model": body.get("model", "gpt-4o-mini"),
        "instructions": body.get("instructions", ""),
        "tools": body.get("tools", []),
        "metadata": body.get("metadata", {}),
    }
    _assistants[assistant["id"]] = assistant
    return assistant


@bp.route("/v1/assistants/<assistant_id>", methods=["DELETE"])
@bp.route("/openai/assistants/<assistant_id>", methods=["DELETE"])
@bp.route("/assistants/<assistant_id>", methods=["DELETE"])
def delete_assistant(assistant_id):
    _assistants.pop(assistant_id, None)
    return {
        "id": assistant_id,
        "object": "assistant.deleted",
        "deleted": True,
    }


@bp.route("/v1/threads", methods=["POST"])
@bp.route("/openai/threads", methods=["POST"])
@bp.route("/threads", methods=["POST"])
def create_thread():
    return {
        "id": "thread-mock-001",
        "object": "thread",
        "created_at": 1700000000,
        "metadata": {},
    }


@bp.route("/v1/threads/<thread_id>/messages", methods=["POST"])
@bp.route("/openai/threads/<thread_id>/messages", methods=["POST"])
@bp.route("/threads/<thread_id>/messages", methods=["POST"])
def create_message(thread_id):
    body = request.get_json(silent=True) or {}
    return {
        "id": "msg-mock-001",
        "object": "thread.message",
        "created_at": 1700000000,
        "thread_id": thread_id,
        "role": body.get("role", "user"),
        "content": [
            {
                "type": "text",
                "text": {"value": body.get("content", ""), "annotations": []},
            }
        ],
        "metadata": {},
    }


def _assistant_tool_call(assistant_id):
    assistant = _assistants.get(assistant_id, {})
    tools = assistant.get("tools", [])
    if not tools:
        return None

    tool = tools[0]
    function = tool.get("function", {})
    return {
        "id": "call_mock_001",
        "type": "function",
        "function": {
            "name": function.get("name", "get_weather"),
            "arguments": json.dumps(mock_tool_arguments(tool)),
        },
    }


def _run_response(body, thread_id, run_id="run-mock-001", status="completed", required_action=None):
    assistant_id = body.get("assistant_id", body.get("agent_id", "asst-mock-001"))
    response = {
        "id": run_id,
        "object": "thread.run",
        "created_at": 1700000000,
        "thread_id": thread_id,
        "assistant_id": assistant_id,
        "status": status,
        "model": body.get("model", "gpt-4o-mini"),
        "instructions": body.get("instructions"),
        "tools": body.get("tools", []),
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 12,
            "total_tokens": 37,
        },
        "metadata": {},
    }
    if required_action is not None:
        response["required_action"] = required_action
    return response


@bp.route("/v1/threads/runs", methods=["POST"])
@bp.route("/openai/threads/runs", methods=["POST"])
@bp.route("/threads/runs", methods=["POST"])
def create_thread_and_run():
    body = request.get_json(silent=True) or {}
    return _run_response(body, thread_id="thread-mock-001")


@bp.route("/v1/threads/<thread_id>/runs", methods=["POST"])
@bp.route("/openai/threads/<thread_id>/runs", methods=["POST"])
@bp.route("/threads/<thread_id>/runs", methods=["POST"])
def create_run(thread_id):
    body = request.get_json(silent=True) or {}
    assistant_id = body.get("assistant_id", body.get("agent_id", "asst-mock-001"))
    tool_call = _assistant_tool_call(assistant_id)
    if tool_call is not None:
        run = _run_response(
            body,
            thread_id=thread_id,
            status="requires_action",
            required_action={
                "type": "submit_tool_outputs",
                "submit_tool_outputs": {
                    "tool_calls": [tool_call],
                },
            },
        )
    else:
        run = _run_response(body, thread_id=thread_id)
    _runs[run["id"]] = run
    return run


@bp.route("/v1/threads/<thread_id>/runs/<run_id>/submit_tool_outputs", methods=["POST"])
@bp.route("/openai/threads/<thread_id>/runs/<run_id>/submit_tool_outputs", methods=["POST"])
@bp.route("/threads/<thread_id>/runs/<run_id>/submit_tool_outputs", methods=["POST"])
def submit_tool_outputs(thread_id, run_id):
    body = request.get_json(silent=True) or {}
    existing_run = _runs.get(run_id)
    run = _run_response(
        existing_run or {},
        thread_id=thread_id,
        run_id=run_id,
        status="completed",
    )
    run["tool_outputs"] = body.get("tool_outputs", [])
    _runs[run_id] = run
    return run


@bp.route("/v1/threads/<thread_id>/runs/<run_id>", methods=["GET"])
@bp.route("/openai/threads/<thread_id>/runs/<run_id>", methods=["GET"])
@bp.route("/threads/<thread_id>/runs/<run_id>", methods=["GET"])
def get_run(thread_id, run_id):
    run = _runs.get(run_id)
    if run is not None:
        return run
    return {
        "id": run_id,
        "object": "thread.run",
        "created_at": 1700000000,
        "thread_id": thread_id,
        "assistant_id": "asst-mock-001",
        "status": "completed",
        "model": "gpt-4o-mini",
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 12,
            "total_tokens": 37,
        },
        "metadata": {},
    }


@bp.route("/v1/threads/<thread_id>/runs", methods=["GET"])
@bp.route("/openai/threads/<thread_id>/runs", methods=["GET"])
@bp.route("/threads/<thread_id>/runs", methods=["GET"])
def list_runs(thread_id):
    runs = [r for r in _runs.values() if r.get("thread_id") == thread_id]
    if not runs:
        runs = [_run_response({}, thread_id=thread_id)]
    return {
        "object": "list",
        "data": runs,
        "first_id": runs[0]["id"],
        "last_id": runs[-1]["id"],
        "has_more": False,
    }


@bp.route("/v1/threads/<thread_id>/messages", methods=["GET"])
@bp.route("/openai/threads/<thread_id>/messages", methods=["GET"])
@bp.route("/threads/<thread_id>/messages", methods=["GET"])
def list_messages(thread_id):
    return {
        "object": "list",
        "data": [
            {
                "id": "msg-mock-002",
                "object": "thread.message",
                "created_at": 1700000001,
                "thread_id": thread_id,
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": {
                            "value": "This is a response from the mock server.",
                            "annotations": [],
                        },
                    }
                ],
                "metadata": {},
            }
        ],
        "first_id": "msg-mock-002",
        "last_id": "msg-mock-002",
        "has_more": False,
    }
