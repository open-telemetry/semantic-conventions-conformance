# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import pytest
from flask.testing import FlaskClient

from genai_mock_server import app


@pytest.fixture
def client() -> FlaskClient:
    return app.test_client()


@pytest.mark.parametrize("tool_key", ["codeExecution", "code_execution"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "/v1beta/models/gemini-2.5-flash:generateContent",
        "/v1/projects/test/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent",
    ],
)
def test_code_execution_returns_a_call_and_result(
    client: FlaskClient, tool_key: str, endpoint: str
) -> None:
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": "Run Python to print one."}]}
        ],
        "tools": [{tool_key: {}}],
    }
    response = client.post(endpoint, json=body)
    assert response.status_code == 200
    assert response.data == client.post(endpoint, json=body).data
    parts = response.json["candidates"][0]["content"]["parts"]
    assert parts == [
        {
            "executableCode": {
                "id": "code-1",
                "code": "print(1)",
                "language": "PYTHON",
            }
        },
        {
            "codeExecutionResult": {
                "id": "code-1",
                "outcome": "OUTCOME_OK",
                "output": "1",
            }
        },
        {"text": "The result is 1."},
    ]
    assert response.json["candidates"][0]["finishReason"] == "STOP"
    assert response.json["usageMetadata"]["promptTokenCount"] > 0


def test_interactions_search_returns_a_linked_call_and_result(
    client: FlaskClient,
) -> None:
    body = {
        "model": "gemini-2.5-flash",
        "input": "Search for OpenTelemetry.",
        "tools": [{"type": "google_search"}],
    }
    response = client.post("/v1beta/interactions", json=body)
    assert response.status_code == 200
    assert response.data == client.post("/v1beta/interactions", json=body).data
    interaction = response.json
    assert interaction["model"] == body["model"]
    assert interaction["status"] == "completed"
    call, result, output = interaction["steps"]
    assert call == {
        "type": "google_search_call",
        "id": "search-1",
        "arguments": {"queries": ["OpenTelemetry"]},
        "search_type": "web_search",
    }
    assert result == {
        "type": "google_search_result",
        "call_id": call["id"],
        "result": [],
        "is_error": False,
    }
    assert output["type"] == "model_output"
    assert output["content"][0]["type"] == "text"
    assert interaction["usage"]["total_output_tokens"] > 0


def test_interactions_without_search_have_only_model_output(
    client: FlaskClient,
) -> None:
    response = client.post("/v1beta/interactions", json={"input": "hi"})
    assert [step["type"] for step in response.json["steps"]] == [
        "model_output"
    ]
