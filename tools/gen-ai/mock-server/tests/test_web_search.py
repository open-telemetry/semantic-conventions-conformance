# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import pytest
from flask.testing import FlaskClient

from genai_mock_server import app


@pytest.fixture
def client() -> FlaskClient:
    return app.test_client()


@pytest.mark.parametrize(
    "tool_type",
    ["web_search", "web_search_preview", "web_search_preview_2025_03_11"],
)
@pytest.mark.parametrize("endpoint", ["/v1/responses", "/openai/v1/responses"])
def test_openai_web_search_is_a_hosted_call(
    client: FlaskClient, tool_type: str, endpoint: str
) -> None:
    body = {
        "model": "gpt-4o-mini",
        "input": "Search for OpenTelemetry.",
        "tools": [{"type": tool_type}],
    }
    response = client.post(endpoint, json=body)
    assert response.status_code == 200
    assert response.data == client.post(endpoint, json=body).data
    result = response.json
    assert result["model"] == body["model"]
    assert result["status"] == "completed"
    call, message = result["output"]
    assert call == {
        "id": "ws_1",
        "type": "web_search_call",
        "status": "completed",
        "action": {"type": "search", "query": "OpenTelemetry"},
    }
    assert message["type"] == "message"
    assert message["content"][0]["type"] == "output_text"
    assert result["usage"]["output_tokens"] > 0


def test_openai_can_fetch_a_stored_web_search_response(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/v1/responses",
        json={"input": "hi", "tools": [{"type": "web_search"}], "store": True},
    )
    assert (
        client.get(f"/v1/responses/{response.json['id']}").json
        == response.json
    )


@pytest.mark.parametrize(
    "tool_type", ["web_search_20250305", "web_search_20260209"]
)
def test_anthropic_web_search_links_its_result(
    client: FlaskClient, tool_type: str
) -> None:
    body = {
        "model": "claude-sonnet-4-20250514",
        "messages": [{"role": "user", "content": "Search for OpenTelemetry."}],
        "tools": [{"type": tool_type, "name": "web_search"}],
    }
    response = client.post("/v1/messages", json=body)
    assert response.status_code == 200
    assert response.data == client.post("/v1/messages", json=body).data
    result = response.json
    assert result["model"] == body["model"]
    assert result["stop_reason"] == "end_turn"
    call, search_result, text = result["content"]
    assert call == {
        "type": "server_tool_use",
        "id": "srvtoolu_01",
        "name": "web_search",
        "input": {"query": "OpenTelemetry"},
    }
    assert search_result["type"] == "web_search_tool_result"
    assert search_result["tool_use_id"] == call["id"]
    assert search_result["content"] == [
        {
            "type": "web_search_result",
            "title": "OpenTelemetry",
            "url": "https://opentelemetry.io/",
            "encrypted_content": "mock-encrypted-content",
        }
    ]
    assert text["type"] == "text"
    assert result["usage"]["server_tool_use"] == {"web_fetch_requests": 0, "web_search_requests": 1}


def test_anthropic_custom_function_named_web_search_stays_a_client_tool(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/v1/messages",
        json={
            "tools": [
                {"name": "web_search", "input_schema": {"type": "object"}}
            ]
        },
    )
    assert response.json["content"][0]["type"] == "tool_use"


@pytest.mark.parametrize(
    "endpoint,tool",
    [
        ("/v1/responses", {"type": "web_search"}),
        (
            "/v1/messages",
            {"type": "web_search_20250305", "name": "web_search"},
        ),
    ],
)
def test_web_search_streaming_is_explicitly_unsupported(
    client: FlaskClient, endpoint: str, tool: dict[str, str]
) -> None:
    response = client.post(endpoint, json={"tools": [tool], "stream": True})
    assert response.status_code == 400
    assert "streaming is not supported" in response.json["error"]["message"]
