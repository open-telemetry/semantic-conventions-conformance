# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import struct

import pytest
from flask.testing import FlaskClient

from genai_mock_server import app


@pytest.fixture
def client() -> FlaskClient:
    return app.test_client()


@pytest.mark.parametrize("limit,expected", [(1, 1), (2, 2), (5, 2)])
def test_retrieve_returns_ranked_documents(
    client: FlaskClient, limit: int, expected: int
) -> None:
    body = {
        "retrievalQuery": {"text": "What is the capital of France?"},
        "retrievalConfiguration": {
            "vectorSearchConfiguration": {"numberOfResults": limit}
        },
    }
    response = client.post("/knowledgebases/KB12345678/retrieve", json=body)
    assert response.status_code == 200
    assert (
        response.data
        == client.post("/knowledgebases/KB12345678/retrieve", json=body).data
    )
    results = response.json["retrievalResults"]
    assert len(results) == expected
    assert results[0]["content"] == {
        "type": "TEXT",
        "text": "Paris is the capital of France.",
    }
    assert results[0]["location"] == {
        "type": "S3",
        "s3Location": {"uri": "s3://KB12345678/document-1.txt"},
    }
    assert all(isinstance(result["score"], float) for result in results)
    assert [result["score"] for result in results] == sorted(
        [result["score"] for result in results], reverse=True
    )


def test_retrieve_defaults_to_two_results(client: FlaskClient) -> None:
    response = client.post(
        "/knowledgebases/KB12345678/retrieve",
        json={"retrievalQuery": {"text": "hi"}},
    )
    assert len(response.json["retrievalResults"]) == 2


@pytest.mark.parametrize("session_id", [None, "existing-session"])
def test_retrieve_and_generate_preserves_the_session(
    client: FlaskClient, session_id: str | None
) -> None:
    body = {"input": {"text": "What is the capital of France?"}}
    if session_id is not None:
        body["sessionId"] = session_id
    response = client.post("/retrieveAndGenerate", json=body)
    assert response.status_code == 200
    assert response.json == {
        "output": {"text": "Paris is the capital of France."},
        "sessionId": session_id or "mock-session-001",
    }
    assert response.data == client.post("/retrieveAndGenerate", json=body).data


@pytest.mark.parametrize("session_id", [None, "existing-session"])
def test_retrieve_and_generate_stream_uses_output_events(
    client: FlaskClient, session_id: str | None
) -> None:
    body = {"input": {"text": "What is the capital of France?"}}
    if session_id is not None:
        body["sessionId"] = session_id
    response = client.post("/retrieveAndGenerateStream", json=body)
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.amazon.eventstream"
    assert response.headers["x-amzn-bedrock-knowledge-base-session-id"] == (
        session_id or "mock-session-001"
    )
    assert (
        response.data
        == client.post("/retrieveAndGenerateStream", json=body).data
    )
    data = response.data
    chunks = []
    offset = 0
    while offset < len(data):
        total_length, headers_length = struct.unpack_from("!II", data, offset)
        headers = data[offset + 12 : offset + 12 + headers_length]
        assert b"\x0b:event-type\x07\x00\x06output" in headers
        chunks.append(
            json.loads(
                data[offset + 12 + headers_length : offset + total_length - 4]
            )
        )
        offset += total_length
    assert chunks == [
        {"text": "Paris is the capital "},
        {"text": "of France."},
    ]
