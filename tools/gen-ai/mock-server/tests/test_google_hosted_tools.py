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


@pytest.mark.parametrize("tool_key", ["googleSearch", "google_search"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "/v1beta/models/gemini-2.5-flash:generateContent",
        "/v1/projects/test/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent",
    ],
)
def test_google_search_returns_a_linked_call_and_result(
    client: FlaskClient, tool_key: str, endpoint: str
) -> None:
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": "Search for OpenTelemetry."}]}
        ],
        "tools": [{tool_key: {}}],
        "toolConfig": {"includeServerSideToolInvocations": True},
    }
    response = client.post(endpoint, json=body)
    assert response.status_code == 200
    assert response.data == client.post(endpoint, json=body).data
    candidate = response.json["candidates"][0]
    call, result, text = candidate["content"]["parts"]
    assert call == {
        "toolCall": {
            "id": "search-1",
            "toolType": "GOOGLE_SEARCH_WEB",
            "args": {"queries": ["OpenTelemetry"]},
        }
    }
    assert result["toolResponse"]["id"] == call["toolCall"]["id"]
    assert result["toolResponse"]["toolType"] == "GOOGLE_SEARCH_WEB"
    assert result["toolResponse"]["response"]["results"]
    assert "text" in text
    assert candidate["groundingMetadata"]["webSearchQueries"] == ["OpenTelemetry"]


def test_google_search_without_opt_in_returns_only_grounded_text(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/v1beta/models/gemini-2.5-flash:generateContent",
        json={"contents": [], "tools": [{"googleSearch": {}}]},
    )
    candidate = response.json["candidates"][0]
    assert [list(part) for part in candidate["content"]["parts"]] == [["text"]]
    assert candidate["groundingMetadata"]["groundingChunks"]


def test_google_search_with_function_declarations_returns_search_then_function_call(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/v1beta/models/gemini-3.8-flash:generateContent",
        json={
            "contents": [
                {"role": "user", "parts": [{"text": "Weather where OTel is from?"}]}
            ],
            "tools": [
                {"googleSearch": {}},
                {
                    "functionDeclarations": [
                        {
                            "name": "get_current_weather",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {"location": {"type": "STRING"}},
                                "required": ["location"],
                            },
                        }
                    ]
                },
            ],
            "toolConfig": {"includeServerSideToolInvocations": True},
        },
    )
    candidate = response.json["candidates"][0]
    call, result, function_call = candidate["content"]["parts"]
    assert call["toolCall"]["toolType"] == "GOOGLE_SEARCH_WEB"
    assert result["toolResponse"]["id"] == call["toolCall"]["id"]
    assert function_call["functionCall"]["name"] == "get_current_weather"
    assert "location" in function_call["functionCall"]["args"]
    assert candidate["groundingMetadata"]["webSearchQueries"] == ["OpenTelemetry"]


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
