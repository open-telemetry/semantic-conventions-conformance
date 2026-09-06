# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Every blueprint answers, and answers the same way twice.

Scenarios depend on the responses being deterministic — that is what replaces
cassette replay — so each case asserts the shape a scenario reads, not just a
200.
"""

import json
import re

import pytest

from genai_mock_server import app

# Inference-style endpoints: same request in, same bytes out.
ENDPOINTS = [
    (
        "openai-chat",
        "post",
        "/v1/chat/completions",
        {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    ),
    (
        "openai-chat-json-schema",
        "post",
        "/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "forecast",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "temperature": {"type": "integer"},
                        },
                    },
                },
            },
        },
    ),
    (
        "openai-embeddings",
        "post",
        "/v1/embeddings",
        {"model": "text-embedding-3-small", "input": "hi"},
    ),
    (
        "openai-embeddings-batched",
        "post",
        "/v1/embeddings",
        {"model": "text-embedding-3-small", "input": ["one", "two"]},
    ),
    (
        "bedrock-converse-tool-use",
        "post",
        "/model/anthropic.claude-v2/converse",
        {
            "messages": [{"role": "user", "content": [{"text": "hi"}]}],
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": "get_current_weather",
                            "inputSchema": {
                                "json": {
                                    "type": "object",
                                    "properties": {
                                        "location": {"type": "string"}
                                    },
                                    "required": ["location"],
                                }
                            },
                        }
                    }
                ]
            },
        },
    ),
    (
        "openai-responses",
        "post",
        "/v1/responses",
        {"model": "gpt-4o-mini", "input": "hi"},
    ),
    (
        "anthropic",
        "post",
        "/v1/messages",
        {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "hi"}],
        },
    ),
    (
        "google-genai",
        "post",
        "/v1beta/models/gemini-2.5-flash:generateContent",
        {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
    ),
    (
        "bedrock",
        "post",
        "/model/amazon.titan-text-express-v1/converse",
        {"messages": [{"role": "user", "content": [{"text": "hi"}]}]},
    ),
    (
        "cohere",
        "post",
        "/v2/chat",
        {"model": "command-r", "messages": [{"role": "user", "content": "hi"}]},
    ),
    (
        "cohere-embed",
        "post",
        "/v2/embed",
        {"model": "embed-v4.0", "texts": ["hi", "there"], "input_type": "search_document"},
    ),
    (
        "mistral-chat",
        "post",
        "/mistral/v1/chat/completions",
        {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": "hi"}],
        },
    ),
    (
        "mistral-fim",
        "post",
        "/mistral/v1/fim/completions",
        {"model": "codestral-latest", "prompt": "def add(a, b):"},
    ),
    (
        "mistral-embeddings",
        "post",
        "/mistral/v1/embeddings",
        {"model": "mistral-embed", "inputs": ["hi", "there"]},
    ),
    (
        "ollama-chat",
        "post",
        "/api/chat",
        {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    ),
    (
        "ollama-embed",
        "post",
        "/api/embed",
        {"model": "nomic-embed-text", "input": ["hi", "there"]},
    ),
]

# Resource-creating endpoints mint a fresh id per call, so only the shape is
# stable. Kept separate rather than loosening the assertion above.
CREATE_ENDPOINTS = [
    ("anthropic-agents", "post", "/v1/agents", {"model": "claude-sonnet-4-20250514"}),
    ("bedrock-agent", "put", "/agents/", {"agentName": "mock-agent"}),
    ("bedrock-agentcore", "post", "/memories/create", {"name": "mock-memory"}),
    ("openai-assistants", "post", "/v1/assistants", {"model": "gpt-4o-mini"}),
    ("mistral-agents", "post", "/mistral/v1/agents", {"model": "mistral-medium-latest"}),
]


@pytest.fixture(name="client")
def _client():
    return app.test_client()


def test_health(client):
    assert client.get("/health").json == {"status": "ok"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [case[1:] for case in ENDPOINTS],
    ids=[case[0] for case in ENDPOINTS],
)
def test_endpoint_answers_deterministically(client, method, path, body):
    first = getattr(client, method)(path, json=body)
    assert first.status_code == 200, first.data

    second = getattr(client, method)(path, json=body)
    assert second.status_code == 200
    assert first.get_data() == second.get_data()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [case[1:] for case in CREATE_ENDPOINTS],
    ids=[case[0] for case in CREATE_ENDPOINTS],
)
def test_create_endpoint_answers_with_a_stable_shape(client, method, path, body):
    first = getattr(client, method)(path, json=body)
    assert first.status_code < 300, first.data

    second = getattr(client, method)(path, json=body)
    assert second.status_code == first.status_code
    assert first.json.keys() == second.json.keys()


def test_chat_echoes_the_requested_model(client):
    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]},
    )
    body = response.json
    assert body["model"] == "gpt-5"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] > 0
    assert body["service_tier"] == "default"


def test_chat_returns_a_tool_call_when_tools_are_offered(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        },
    )
    tool_calls = response.json["choices"][0]["message"]["tool_calls"]
    assert [call["function"]["name"] for call in tool_calls] == ["get_weather"]
    assert "location" in json.loads(tool_calls[0]["function"]["arguments"])


def test_bedrock_converse_returns_a_tool_use_when_tools_are_offered(client):
    body = {
        "messages": [
            {"role": "user", "content": [{"text": "weather in Seattle?"}]}
        ],
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": "get_current_weather",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {"location": {"type": "string"}},
                                "required": ["location"],
                            }
                        },
                    }
                }
            ]
        },
    }
    response = client.post("/model/anthropic.claude-v2/converse", json=body)
    assert response.json["stopReason"] == "tool_use"
    tool_use = response.json["output"]["message"]["content"][0]["toolUse"]
    assert tool_use["name"] == "get_current_weather"
    assert tool_use["input"] == {"location": "Seattle"}

    # Once the result comes back the model answers instead of calling again.
    body["messages"].append(
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use["toolUseId"],
                        "content": [{"text": "70 degrees and sunny"}],
                    }
                }
            ],
        }
    )
    answer = client.post("/model/anthropic.claude-v2/converse", json=body)
    assert answer.json["stopReason"] == "end_turn"


def test_bedrock_converse_calls_the_tool_the_request_chose(client):
    def tool(name):
        return {
            "toolSpec": {
                "name": name,
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            }
        }

    body = {
        "messages": [{"role": "user", "content": [{"text": "hi"}]}],
        "toolConfig": {
            "tools": [tool("get_weather"), tool("get_time")],
            "toolChoice": {"tool": {"name": "get_time"}},
        },
    }
    response = client.post("/model/anthropic.claude-v2/converse", json=body)
    content = response.json["output"]["message"]["content"][0]
    assert content["toolUse"]["name"] == "get_time"


def test_bedrock_converse_answers_when_no_tool_is_offered(client):
    # Inventing a call would hand the client a tool it does not have.
    response = client.post(
        "/model/anthropic.claude-v2/converse",
        json={
            "messages": [{"role": "user", "content": [{"text": "hi"}]}],
            "toolConfig": {"tools": []},
        },
    )
    assert response.json["stopReason"] == "end_turn"


def test_embeddings_treat_token_ids_as_one_input(client):
    response = client.post(
        "/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": [1, 2, 3, 4, 5]},
    )
    assert len(response.json["data"]) == 1


def test_embeddings_reject_an_empty_input(client):
    response = client.post(
        "/v1/embeddings", json={"model": "text-embedding-3-small", "input": []}
    )
    assert response.status_code == 400


def test_embeddings_survive_an_unusable_dimension_count(client):
    response = client.post(
        "/v1/embeddings",
        json={
            "model": "text-embedding-3-small",
            "input": "hi",
            "dimensions": "not-a-number",
        },
    )
    assert response.status_code == 200
    assert len(response.json["data"][0]["embedding"]) == 256


def test_chat_reports_the_service_tier_that_served_the_request(client):
    def tier(requested):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                **({"service_tier": requested} if requested else {}),
            },
        )
        return response.json["service_tier"]

    assert tier(None) == "default"
    # "auto" is a request for the API to choose, never the tier it answers on.
    assert tier("auto") == "default"
    assert tier("flex") == "flex"


def test_streaming_chat_reports_the_service_tier(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "service_tier": "priority",
            "stream": True,
        },
    )
    first = json.loads(
        response.get_data(as_text=True).split("\n\n")[0].removeprefix("data: ")
    )
    assert first["service_tier"] == "priority"


def test_json_schema_follows_refs_and_skips_null_branches(client):
    # The shape a schema generated from a class has.
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "forecast",
                    "schema": {
                        "type": "object",
                        "$defs": {
                            "Day": {
                                "type": "object",
                                "properties": {"summary": {"type": "string"}},
                            }
                        },
                        "properties": {
                            "days": {
                                "type": "array",
                                "items": {"$ref": "#/$defs/Day"},
                            },
                            "note": {
                                "anyOf": [
                                    {"type": "null"},
                                    {"type": "string"},
                                ]
                            },
                            "issued": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
    )
    answer = json.loads(response.json["choices"][0]["message"]["content"])
    assert answer == {
        "days": [{"summary": "mock-summary"}],
        "note": "mock-note",
        "issued": "2023-11-14T22:13:20Z",
    }


def test_json_schema_cuts_off_a_self_referencing_model(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "node",
                    "schema": {
                        "type": "object",
                        "$defs": {
                            "Node": {
                                "type": "object",
                                "properties": {"child": {"$ref": "#/$defs/Node"}},
                            }
                        },
                        "properties": {"root": {"$ref": "#/$defs/Node"}},
                    },
                },
            },
        },
    )
    # Only that it terminates matters, not the depth it stops at.
    assert response.status_code == 200
    json.loads(response.json["choices"][0]["message"]["content"])


def test_google_answers_a_response_schema_with_matching_json(client):
    response = client.post(
        "/v1beta/models/gemini-2.0-flash:generateContent",
        json={
            "contents": [{"role": "user", "parts": [{"text": "weather?"}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                # Gemini spells its schema in upper-case enum names.
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "location": {"type": "STRING"},
                        "temperature": {"type": "INTEGER"},
                    },
                },
            },
        },
    )
    text = response.json["candidates"][0]["content"]["parts"][0]["text"]
    assert json.loads(text) == {"location": "Seattle", "temperature": 1}


def test_google_batch_embeddings_answer_one_vector_per_request(client):
    response = client.post(
        "/v1beta/models/text-embedding-004:batchEmbedContents",
        json={
            "requests": [
                {"content": {"parts": [{"text": "one"}]}},
                {"content": {"parts": [{"text": "two"}]}},
            ]
        },
    )
    assert len(response.json["embeddings"]) == 2
    assert response.json["usageMetadata"]["promptTokenCount"] == 16


def test_embeddings_answer_one_vector_per_input(client):
    response = client.post(
        "/v1/embeddings",
        json={
            "model": "text-embedding-3-small",
            "input": ["one", "two", "three"],
            "dimensions": 8,
        },
    )
    data = response.json["data"]
    assert [entry["index"] for entry in data] == [0, 1, 2]
    assert all(len(entry["embedding"]) == 8 for entry in data)
    assert response.json["usage"]["prompt_tokens"] == 24


def test_chat_answers_a_json_schema_with_a_matching_object(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "how is the weather?"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "forecast",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "temperature": {"type": "integer"},
                            "conditions": {"enum": ["sunny", "rainy"]},
                            "days": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"summary": {"type": "string"}},
                                },
                            },
                        },
                        "required": ["location", "temperature", "conditions", "days"],
                    },
                },
            },
        },
    )
    answer = json.loads(response.json["choices"][0]["message"]["content"])
    assert answer == {
        "location": "Seattle",
        "temperature": 1,
        "conditions": "sunny",
        "days": [{"summary": "mock-summary"}],
    }


def test_chat_streams_when_asked(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    chunks = response.get_data(as_text=True)
    assert chunks.startswith("data: ")
    assert chunks.rstrip().endswith("data: [DONE]")


def test_streaming_chat_calls_an_offered_tool(client):
    """A framework that only streams still has to see the tool exchange."""
    tool = {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        },
    }
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "tools": [tool],
            "stream": True,
        },
    )
    deltas = [
        json.loads(line[len("data: ") :])
        for line in response.get_data(as_text=True).splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    calls = [
        call
        for chunk in deltas
        for call in chunk["choices"][0]["delta"].get("tool_calls", [])
    ]
    assert [call["function"].get("name") for call in calls] == [
        "get_current_weather",
        None,
    ]
    assert json.loads("".join(call["function"]["arguments"] for call in calls)) == {
        "location": "Seattle"
    }
    assert deltas[-1]["choices"][0]["finish_reason"] == "tool_calls"


def test_streaming_chat_answers_once_the_tool_has_replied(client):
    """The second round trip is an answer, not the same call again."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "weather in Seattle?"},
                {"role": "assistant", "tool_calls": []},
                {"role": "tool", "content": "70 degrees", "tool_call_id": "call_mock_001"},
            ],
            "tools": [{"type": "function", "function": {"name": "get_current_weather"}}],
            "stream": True,
        },
    )
    body = response.get_data(as_text=True)
    assert "tool_calls" not in body
    assert '"finish_reason": "stop"' in body


def test_mistral_chat_calls_an_offered_tool(client):
    """The id has to be nine alphanumerics or Mistral rejects it coming back."""
    response = client.post(
        "/mistral/v1/chat/completions",
        json={
            "model": "mistral-medium-latest",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        },
    )
    call = response.json["choices"][0]["message"]["tool_calls"][0]
    assert re.fullmatch(r"[A-Za-z0-9]{9}", call["id"])
    assert call["function"]["name"] == "get_current_weather"
    assert json.loads(call["function"]["arguments"]) == {"location": "Seattle"}
    assert response.json["choices"][0]["finish_reason"] == "tool_calls"
    assert response.json["model"] == "mistral-medium-latest"


def test_mistral_chat_answers_once_the_tool_has_replied(client):
    response = client.post(
        "/mistral/v1/chat/completions",
        json={
            "model": "mistral-small-latest",
            "messages": [
                {"role": "user", "content": "weather in Seattle?"},
                {
                    "role": "tool",
                    "name": "get_current_weather",
                    "content": "70 degrees",
                    "tool_call_id": "callmock1",
                },
            ],
            "tools": [{"type": "function", "function": {"name": "get_current_weather"}}],
        },
    )
    assert response.json["choices"][0]["message"]["tool_calls"] is None
    assert response.json["choices"][0]["finish_reason"] == "stop"


def test_mistral_chat_meters_audio_input_in_seconds(client):
    """Mistral has no audio token count: the usage figure is a duration."""
    response = client.post(
        "/mistral/v1/chat/completions",
        json={
            "model": "voxtral-mini-latest",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "what do you hear?"},
                        {"type": "input_audio", "input_audio": "bW9jaw=="},
                    ],
                }
            ],
        },
    )
    assert response.json["usage"]["prompt_audio_seconds"] > 0


def test_mistral_chat_streams_the_same_answer_it_would_return(client):
    """Streamed and non-streamed are one response, so they cannot drift."""
    body = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": "hi"}],
    }
    complete = client.post("/mistral/v1/chat/completions", json=body)
    streamed = client.post("/mistral/v1/chat/completions", json={**body, "stream": True})
    chunks = [
        json.loads(line[len("data: ") :])
        for line in streamed.get_data(as_text=True).splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    content = "".join(
        chunk["choices"][0]["delta"].get("content", "") for chunk in chunks
    )
    assert content.strip() == complete.json["choices"][0]["message"]["content"]
    assert chunks[-1]["usage"] == complete.json["usage"]
    assert streamed.get_data(as_text=True).rstrip().endswith("data: [DONE]")


def test_mistral_answers_a_json_schema_request_with_that_schema(client):
    response = client.post(
        "/mistral/v1/chat/completions",
        json={
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": "weather?"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "forecast",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "temperature": {"type": "integer"},
                        },
                        "required": ["location", "temperature"],
                    },
                },
            },
        },
    )
    answer = json.loads(response.json["choices"][0]["message"]["content"])
    assert answer == {"location": "Seattle", "temperature": 1}


def test_mistral_embeddings_answer_one_vector_per_input(client):
    response = client.post(
        "/mistral/v1/embeddings",
        json={
            "model": "mistral-embed",
            "inputs": ["one", "two", "three"],
            "output_dimension": 8,
        },
    )
    data = response.json["data"]
    assert [entry["index"] for entry in data] == [0, 1, 2]
    assert all(len(entry["embedding"]) == 8 for entry in data)


# Azure routes the same operation under a deployment path; instrumentations
# read the URL, so the alias has to serve the identical body.
def test_azure_deployment_path_matches_the_plain_one(client):
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
    plain = client.post("/v1/chat/completions", json=body)
    deployment = client.post(
        "/openai/deployments/gpt-4o-mini/chat/completions", json=body
    )
    assert deployment.get_data() == plain.get_data()


# ─── Behaviours a scenario elsewhere depends on ─────────────────────────────


def test_responses_report_a_terminal_status(client):
    """Instrumentation reads `status` to know the response finished."""
    response = client.post(
        "/v1/responses", json={"model": "gpt-4o-mini", "input": "hi"}
    )

    assert response.json["status"] == "completed"


# qwen-agent and other Hermes/Nous-protocol clients advertise tools inside a
# <tools> block in the system prompt and expect the call back as <tool_call>
# JSON in the assistant content — not through the `tools` request field.
HERMES_SYSTEM = """You may call tools.

<tools>
{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}}
</tools>

Return calls as <tool_call>{"name": ..., "arguments": ...}</tool_call>.
"""


def _hermes_request(*extra_messages):
    return {
        "model": "qwen-max",
        "messages": [
            {"role": "system", "content": HERMES_SYSTEM},
            {"role": "user", "content": "weather in Seattle?"},
            *extra_messages,
        ],
    }


def test_text_protocol_tools_get_a_tool_call_in_the_content(client):
    response = client.post("/v1/chat/completions", json=_hermes_request())

    content = response.json["choices"][0]["message"]["content"]
    assert content.startswith("<tool_call>")
    call = json.loads(content.removeprefix("<tool_call>").removesuffix("</tool_call>"))
    assert call["name"] == "get_weather"
    assert "location" in call["arguments"]


def test_text_protocol_does_not_loop_once_the_tool_has_answered(client):
    """A second call after the result must not ask for the tool again."""
    answered = _hermes_request(
        {"role": "assistant", "content": '<tool_call>\n{"name": "get_weather"}\n</tool_call>'},
        {"role": "user", "content": "<tool_response>\n70 degrees\n</tool_response>"},
    )

    response = client.post("/v1/chat/completions", json=answered)

    content = response.json["choices"][0]["message"]["content"]
    assert "<tool_call>" not in content


def test_chat_reports_audio_tokens_when_audio_is_requested(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-audio-preview",
            "modalities": ["text", "audio"],
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    usage = response.json["usage"]
    assert usage["completion_tokens_details"]["audio_tokens"] > 0
    assert usage["prompt_tokens_details"]["audio_tokens"] == 0

    message = response.json["choices"][0]["message"]
    assert message["audio"]["transcript"]
    assert message["content"] is None


def test_chat_reports_audio_tokens_for_audio_input(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-audio-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "input_audio", "input_audio": {"data": "bW9jaw==", "format": "wav"}}],
                }
            ],
        },
    )

    usage = response.json["usage"]
    assert usage["prompt_tokens_details"]["audio_tokens"] > 0
    # Text-only output was requested, so no audio is generated.
    assert usage["completion_tokens_details"]["audio_tokens"] == 0
    assert "audio" not in response.json["choices"][0]["message"]


def test_responses_reports_cache_write_tokens(client):
    response = client.post("/v1/responses", json={"model": "gpt-4o-mini", "input": "hi"})

    details = response.json["usage"]["input_tokens_details"]
    assert details["cache_write_tokens"] > 0
    assert details["cached_tokens"] > 0


def test_google_reports_a_cached_and_per_modality_breakdown(client):
    response = client.post(
        "/v1beta/models/gemini-2.0-flash:generateContent",
        json={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
    )

    usage = response.json["usageMetadata"]
    assert usage["cachedContentTokenCount"] > 0
    assert [d["modality"] for d in usage["promptTokensDetails"]] == ["TEXT"]
    assert [d["modality"] for d in usage["cacheTokensDetails"]] == ["TEXT"]
    assert [d["modality"] for d in usage["candidatesTokensDetails"]] == ["TEXT"]


def test_google_bills_tool_use_tokens_separately_from_the_prompt(client):
    tools = [{"functionDeclarations": [{"name": "get_weather"}]}]
    request = {"contents": [{"role": "user", "parts": [{"text": "weather?"}]}], "tools": tools}

    call = client.post("/v1beta/models/gemini-2.0-flash:generateContent", json=request).json
    usage = call["usageMetadata"]
    assert usage["toolUsePromptTokenCount"] > 0
    # Tool-use tokens are their own component of the total, not part of the prompt.
    expected = (
        usage["promptTokenCount"]
        + usage["candidatesTokenCount"]
        + usage["toolUsePromptTokenCount"]
        + usage["thoughtsTokenCount"]
    )
    assert usage["totalTokenCount"] == expected


def test_google_answers_in_text_once_the_tool_has_answered(client):
    answered = {
        "contents": [
            {"role": "user", "parts": [{"text": "weather?"}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "get_weather", "response": {"temp": 70}}}]},
        ],
        "tools": [{"functionDeclarations": [{"name": "get_weather"}]}],
    }

    body = client.post("/v1beta/models/gemini-2.0-flash:generateContent", json=answered).json

    parts = body["candidates"][0]["content"]["parts"]
    assert all("functionCall" not in part for part in parts)
    assert body["usageMetadata"]["toolUsePromptTokenCount"] > 0


def test_google_breaks_usage_down_by_input_and_output_modality(client):
    blob = {"mimeType": "image/png", "data": "bW9jaw=="}
    response = client.post(
        "/v1beta/models/gemini-2.0-flash:generateContent",
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "describe"},
                        {"inlineData": blob},
                        {"inlineData": blob},
                        {"inlineData": {"mimeType": "audio/wav", "data": "bW9jaw=="}},
                    ],
                }
            ],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        },
    )

    usage = response.json["usageMetadata"]
    # One entry per modality, not per part: the two images are summed.
    prompt = {d["modality"]: d["tokenCount"] for d in usage["promptTokensDetails"]}
    assert set(prompt) == {"TEXT", "IMAGE", "AUDIO"}
    assert prompt["IMAGE"] == 2 * 258
    assert sum(prompt.values()) == usage["promptTokenCount"]

    assert [d["modality"] for d in usage["candidatesTokensDetails"]] == ["TEXT", "IMAGE"]
    assert sum(d["tokenCount"] for d in usage["candidatesTokensDetails"]) == usage["candidatesTokenCount"]
    assert usage["cachedContentTokenCount"] < usage["promptTokenCount"]


def test_ollama_chat_calls_an_offered_tool(client):
    """Ollama carries the arguments as an object, not as a JSON string."""
    response = client.post(
        "/api/chat",
        json={
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        },
    )
    call = response.json["message"]["tool_calls"][0]
    assert call["function"]["name"] == "get_current_weather"
    assert call["function"]["arguments"] == {"location": "Seattle"}


def test_ollama_chat_answers_once_the_tool_has_replied(client):
    response = client.post(
        "/api/chat",
        json={
            "model": "llama3.2",
            "messages": [
                {"role": "user", "content": "weather in Seattle?"},
                {"role": "tool", "content": "70 degrees"},
            ],
            "stream": False,
            "tools": [{"type": "function", "function": {"name": "get_current_weather"}}],
        },
    )
    assert "tool_calls" not in response.json["message"]
    assert response.json["done_reason"] == "stop"


def test_ollama_streams_newline_delimited_json(client):
    """Ollama streams NDJSON, not SSE, and only the last line is done."""
    response = client.post(
        "/api/chat",
        json={
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    lines = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
    assert [line["done"] for line in lines] == [False] * (len(lines) - 1) + [True]
    streamed = "".join(line["message"]["content"] for line in lines).strip()
    assert streamed == "This is a response from the mock server."
    assert lines[-1]["eval_count"] == 12


def test_ollama_answers_a_format_request_with_that_schema(client):
    """`format` carries the schema itself, so the answer is built from it."""
    response = client.post(
        "/api/chat",
        json={
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "temperature": {"type": "integer"},
                },
            },
        },
    )
    assert json.loads(response.json["message"]["content"]) == {
        "location": "Seattle",
        "temperature": 1,
    }


def test_ollama_embeddings_answer_one_vector_per_input(client):
    response = client.post(
        "/api/embed",
        json={"model": "nomic-embed-text", "input": ["one", "two"], "dimensions": 64},
    )
    assert len(response.json["embeddings"]) == 2
    assert len(response.json["embeddings"][0]) == 64
    assert response.json["prompt_eval_count"] == 16


def test_cohere_chat_calls_an_offered_tool(client):
    """Cohere narrates the call in a tool_plan field of its own."""
    response = client.post(
        "/v2/chat",
        json={
            "model": "command-a-03-2025",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        },
    )
    call = response.json["message"]["tool_calls"][0]
    assert call["function"]["name"] == "get_current_weather"
    assert json.loads(call["function"]["arguments"]) == {"location": "Seattle"}
    assert response.json["message"]["tool_plan"]
    assert response.json["finish_reason"] == "TOOL_CALL"


def test_cohere_chat_answers_once_the_tool_has_replied(client):
    response = client.post(
        "/v2/chat",
        json={
            "model": "command-a-03-2025",
            "messages": [
                {"role": "user", "content": "weather in Seattle?"},
                {"role": "tool", "tool_call_id": "x", "content": "70 degrees"},
            ],
            "tools": [{"type": "function", "function": {"name": "get_current_weather"}}],
        },
    )
    assert "tool_calls" not in response.json["message"]
    assert response.json["finish_reason"] == "COMPLETE"


def test_cohere_chat_streams_the_same_answer_it_would_return(client):
    streamed = client.post(
        "/v2/chat",
        json={
            "model": "command-a-03-2025",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    ).get_data(as_text=True)
    events = [
        json.loads(line[len("data: ") :])
        for line in streamed.splitlines()
        if line.startswith("data: ")
    ]
    text = "".join(
        event["delta"]["message"]["content"]["text"]
        for event in events
        if event["type"] == "content-delta"
    ).strip()
    assert text == "This is a response from the mock server."
    assert events[-1]["delta"]["finish_reason"] == "COMPLETE"


def test_cohere_streams_a_tool_call_it_would_have_returned(client):
    """The streamed call has to reassemble into the non-streamed one."""
    streamed = client.post(
        "/v2/chat",
        json={
            "model": "command-a-03-2025",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        },
    ).get_data(as_text=True)
    events = [
        json.loads(line[len("data: ") :])
        for line in streamed.splitlines()
        if line.startswith("data: ")
    ]
    by_type = {event["type"]: event for event in events}
    assert "tool-plan-delta" in by_type
    start = by_type["tool-call-start"]["delta"]["message"]["tool_calls"]
    assert start["function"]["name"] == "get_current_weather"
    arguments = "".join(
        event["delta"]["message"]["tool_calls"]["function"]["arguments"]
        for event in events
        if event["type"] in ("tool-call-start", "tool-call-delta")
    )
    assert json.loads(arguments) == {"location": "Seattle"}
    assert "tool-call-end" in by_type
    assert events[-1]["delta"]["finish_reason"] == "TOOL_CALL"


def test_cohere_answers_a_json_object_request_with_its_schema(client):
    response = client.post(
        "/v2/chat",
        json={
            "model": "command-a-03-2025",
            "messages": [{"role": "user", "content": "weather in Seattle?"}],
            "response_format": {
                "type": "json_object",
                "json_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "temperature": {"type": "integer"},
                    },
                },
            },
        },
    )
    assert json.loads(response.json["message"]["content"][0]["text"]) == {
        "location": "Seattle",
        "temperature": 1,
    }


def test_cohere_embeddings_answer_one_vector_per_input(client):
    response = client.post(
        "/v2/embed",
        json={
            "model": "embed-v4.0",
            "texts": ["one", "two"],
            "input_type": "search_document",
            "output_dimension": 64,
        },
    )
    vectors = response.json["embeddings"]["float"]
    assert len(vectors) == 2
    assert len(vectors[0]) == 64
