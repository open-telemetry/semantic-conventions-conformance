"""AWS Bedrock Agent control-plane and Agent Runtime-compatible endpoints.

Serves both the ``bedrock-agent`` (control plane) and ``bedrock-agent-runtime``
(data plane) operations against a single mock URL, since both boto3 clients
accept the same ``endpoint_url``.
"""

import base64
import json

from flask import Blueprint, Response, request

from ._common import encode_aws_event_stream_message

bp = Blueprint("bedrock_agent", __name__)

_AGENT_COUNTER = 0


# Control plane -------------------------------------------------------------


@bp.route("/agents/", methods=["PUT"])
def bedrock_agent_create():
    """Handle Bedrock Agent CreateAgent."""
    global _AGENT_COUNTER
    _AGENT_COUNTER += 1
    body = request.get_json(silent=True) or {}
    agent_id = f"MOCKAGENTID{_AGENT_COUNTER:03d}"
    agent = {
        "agentId": agent_id,
        "agentName": body.get("agentName", "unnamed-agent"),
        "agentArn": f"arn:aws:bedrock:us-east-1:123456789012:agent/{agent_id}",
        "agentVersion": "DRAFT",
        "agentStatus": "CREATING",
        "foundationModel": body.get("foundationModel"),
        "instruction": body.get("instruction"),
        "description": body.get("description"),
        "idleSessionTTLInSeconds": body.get("idleSessionTTLInSeconds", 600),
        "agentResourceRoleArn": body.get(
            "agentResourceRoleArn", "arn:aws:iam::123456789012:role/service-role/AmazonBedrockExecutionRoleForAgents"
        ),
        "createdAt": "2026-04-08T00:00:00Z",
        "updatedAt": "2026-04-08T00:00:00Z",
    }
    return Response(
        json.dumps({"agent": {k: v for k, v in agent.items() if v is not None}}),
        status=202,
        mimetype="application/json",
    )


# Data plane ----------------------------------------------------------------


def _stream_invoke(agent_id, alias_id, session_id, enable_trace=False):
    """Yield Bedrock Agent invoke_agent event-stream chunks in binary format."""
    events = []
    # The agent response is delivered as chunk events with base64-encoded bytes
    text = "This is a response from the mock server."
    events.append(("chunk", {"bytes": base64.b64encode(text.encode("utf-8")).decode("ascii")}))
    if enable_trace:
        events.append(
            (
                "trace",
                {
                    "agentId": agent_id,
                    "agentAliasId": alias_id,
                    "agentVersion": "1",
                    "sessionId": session_id,
                    "eventTime": "2026-04-08T00:00:00Z",
                    "trace": {
                        "customOrchestrationTrace": {
                            "traceId": "trace-mock-001",
                            "event": {
                                "text": "Mock orchestration trace",
                            },
                        }
                    },
                },
            )
        )
    for event_type, body in events:
        payload = json.dumps(body).encode("utf-8")
        yield encode_aws_event_stream_message(event_type, payload)


@bp.route("/agents/<agent_id>/agentAliases/<alias_id>/sessions/<session_id>/text", methods=["POST"])
def bedrock_agent_invoke(agent_id, alias_id, session_id):
    """Handle Bedrock Agent Runtime InvokeAgent."""
    body = request.get_json(silent=True) or {}
    return Response(
        _stream_invoke(
            agent_id,
            alias_id,
            session_id,
            enable_trace=bool(body.get("enableTrace")),
        ),
        mimetype="application/vnd.amazon.eventstream",
        headers={
            "x-amzn-bedrock-agent-session-id": session_id,
            "x-amz-bedrock-agent-content-type": "application/json",
        },
    )


@bp.route("/knowledgebases/<knowledge_base_id>/retrieve", methods=["POST"])
def bedrock_retrieve(knowledge_base_id: str) -> dict[str, object]:
    body = request.get_json(silent=True) or {}
    configuration = (body.get("retrievalConfiguration") or {}).get("vectorSearchConfiguration") or {}
    limit = configuration.get("numberOfResults", 2)
    documents = [
        ("Paris is the capital of France.", 0.87),
        ("France is in Western Europe.", 0.61),
    ]
    return {
        "retrievalResults": [
            {
                "content": {"type": "TEXT", "text": text},
                "location": {
                    "type": "S3",
                    "s3Location": {"uri": f"s3://{knowledge_base_id}/document-{index}.txt"},
                },
                "score": score,
            }
            for index, (text, score) in enumerate(documents[:limit], start=1)
        ]
    }


@bp.route("/retrieveAndGenerate", methods=["POST"])
def bedrock_retrieve_and_generate() -> dict[str, object]:
    body = request.get_json(silent=True) or {}
    return {
        "output": {"text": "Paris is the capital of France."},
        "sessionId": body.get("sessionId", "mock-session-001"),
    }


@bp.route("/retrieveAndGenerateStream", methods=["POST"])
def bedrock_retrieve_and_generate_stream() -> Response:
    body = request.get_json(silent=True) or {}
    chunks = (
        encode_aws_event_stream_message("output", json.dumps({"text": text}).encode("utf-8"))
        for text in ["Paris is the capital ", "of France."]
    )
    return Response(
        chunks,
        mimetype="application/vnd.amazon.eventstream",
        headers={
            "x-amzn-bedrock-knowledge-base-session-id": body.get("sessionId", "mock-session-001"),
        },
    )
