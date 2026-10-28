# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from flask.testing import FlaskClient

from genai_mock_server import app

_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    },
}


@pytest.fixture
def client() -> FlaskClient:
    return app.test_client()


@pytest.fixture
def assistant_with_tool(client: FlaskClient):
    assistant = client.post(
        "/v1/assistants", json={"model": "gpt-4o-mini", "tools": [_TOOL]}
    ).json
    yield assistant["id"]
    client.delete(f"/v1/assistants/{assistant['id']}")


def _events(response) -> list[tuple[str, object]]:
    assert response.mimetype == "text/event-stream"
    body = response.get_data(as_text=True)
    assert body.endswith("event: done\ndata: [DONE]\n\n")
    events = []
    for block in body.strip().split("\n\n")[:-1]:
        event_line, data_line = block.split("\n")
        assert event_line.startswith("event: ")
        assert data_line.startswith("data: ")
        events.append(
            (event_line[len("event: ") :], json.loads(data_line[len("data: ") :]))
        )
    return events


def test_streamed_run_stops_at_requires_action_when_tools_are_offered(
    client: FlaskClient, assistant_with_tool: str
) -> None:
    body = {"assistant_id": assistant_with_tool}
    plain = client.post("/v1/threads/thread-mock-001/runs", json=body).json

    events = _events(
        client.post(
            "/v1/threads/thread-mock-001/runs", json={**body, "stream": True}
        )
    )

    assert [name for name, _ in events] == [
        "thread.run.created",
        "thread.run.queued",
        "thread.run.in_progress",
        "thread.run.step.created",
        "thread.run.step.in_progress",
        "thread.run.requires_action",
    ]
    assert events[-1][1] == plain


def test_streamed_tool_outputs_complete_the_run(
    client: FlaskClient, assistant_with_tool: str
) -> None:
    run = client.post(
        "/v1/threads/thread-mock-001/runs",
        json={"assistant_id": assistant_with_tool, "stream": True},
    )
    run_id = _events(run)[-1][1]["id"]

    events = _events(
        client.post(
            f"/v1/threads/thread-mock-001/runs/{run_id}/submit_tool_outputs",
            json={
                "tool_outputs": [
                    {"tool_call_id": "call_mock_001", "output": "sunny"}
                ],
                "stream": True,
            },
        )
    )

    names = [name for name, _ in events]
    assert names[:2] == ["thread.run.queued", "thread.run.in_progress"]
    assert names[-1] == "thread.run.completed"
    text = "".join(
        data["delta"]["content"][0]["text"]["value"]
        for name, data in events
        if name == "thread.message.delta"
    )
    message = next(d for n, d in events if n == "thread.message.completed")
    assert message["content"][0]["text"]["value"] == text
    completed = events[-1][1]
    assert completed["status"] == "completed"
    assert completed["usage"]["total_tokens"] == 37
    retrieved = client.get(f"/v1/threads/thread-mock-001/runs/{run_id}").json
    assert retrieved == completed


def test_streamed_run_without_tools_answers_in_one_stream(
    client: FlaskClient,
) -> None:
    events = _events(
        client.post(
            "/v1/threads/thread-mock-001/runs",
            json={"assistant_id": "asst-unknown", "stream": True},
        )
    )

    names = [name for name, _ in events]
    assert names[0] == "thread.run.created"
    assert "thread.run.requires_action" not in names
    assert "thread.message.completed" in names
    assert names[-1] == "thread.run.completed"


def test_streamed_create_thread_and_run_starts_with_the_thread(
    client: FlaskClient,
) -> None:
    events = _events(
        client.post(
            "/v1/threads/runs",
            json={"assistant_id": "asst-mock-001", "stream": True},
        )
    )

    assert events[0][0] == "thread.created"
    assert events[0][1]["id"] == "thread-mock-001"
    assert events[-1][0] == "thread.run.completed"
