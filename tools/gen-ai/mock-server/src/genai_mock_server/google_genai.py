"""Google GenAI / Vertex AI -compatible endpoints."""

import copy
import json

from flask import Blueprint, Response, request

from ._common import mock_json_schema_value, mock_tool_arguments

bp = Blueprint("google_genai", __name__)


RESPONSE = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [{"text": "This is a response from the mock server."}],
            },
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 25,
        "cachedContentTokenCount": 10,
        "candidatesTokenCount": 12,
        "thoughtsTokenCount": 3,
        "totalTokenCount": 40,
        "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 25}],
        "cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 10}],
        "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 12}],
    },
    "modelVersion": "gemini-2.0-flash",
    "responseId": "resp-mock-001",
}

FUNCTION_CALL_RESPONSE = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "id": "call_mock_001",
                            "name": "get_weather",
                            "args": {"location": "Seattle"},
                        }
                    }
                ],
            },
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 25,
        # Tool-use tokens are a separate component of the total, not part of
        # promptTokenCount (see GenerateContentResponseUsageMetadata).
        "toolUsePromptTokenCount": 8,
        "candidatesTokenCount": 12,
        "thoughtsTokenCount": 3,
        # total = prompt + candidates + tool_use + thoughts
        "totalTokenCount": 48,
        "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 25}],
        "toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 8}],
        "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 12}],
    },
    "modelVersion": "gemini-2.0-flash",
    "responseId": "resp-mock-001",
}

# Returned for the turn that follows a functionResponse: the model answers in
# text, and the tool round-trip is billed as tool-use prompt tokens.
FUNCTION_RESPONSE = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [{"text": "This is a response from the mock server using tools."}],
            },
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 25,
        "toolUsePromptTokenCount": 8,
        "candidatesTokenCount": 12,
        "thoughtsTokenCount": 3,
        "totalTokenCount": 48,
        "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 25}],
        "toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 8}],
        "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 12}],
    },
    "modelVersion": "gemini-2.0-flash",
    "responseId": "resp-mock-001",
}

EMBEDDING_RESPONSE = {
    "embedding": {
        "values": [0.001] * 256,
    },
    "usageMetadata": {"promptTokenCount": 8},
}

BATCH_EMBEDDING_RESPONSE = {
    "embeddings": [
        {"values": [0.001] * 256},
    ],
    "usageMetadata": {"promptTokenCount": 8},
}


# Per-modality mock token counts, keyed by MIME-type prefix, used to derive a
# realistic per-modality usage breakdown from the request's media parts.
_MIME_MODALITY = (
    ("image/", ("IMAGE", 258)),
    ("audio/", ("AUDIO", 120)),
)

# Mock candidate token counts per generated output modality.
_OUTPUT_MODALITY = {
    "TEXT": 12,
    "IMAGE": 1290,
    "AUDIO": 240,
}


def _request_media_modalities(body):
    """Token count per media modality in the request, summed over all parts of that modality."""
    totals = {}
    for content in body.get("contents") or []:
        for part in content.get("parts") or []:
            blob = (
                part.get("inlineData") or part.get("inline_data") or part.get("fileData") or part.get("file_data") or {}
            )
            mime = blob.get("mimeType") or blob.get("mime_type") or ""
            for prefix, (modality, count) in _MIME_MODALITY:
                if mime.startswith(prefix):
                    totals[modality] = totals.get(modality, 0) + count
                    break
    return totals


def _response_modalities(body):
    """Requested output modalities, de-duplicated in request order (defaults to TEXT)."""
    cfg = body.get("generationConfig") or body.get("generation_config") or {}
    mods = cfg.get("responseModalities") or cfg.get("response_modalities") or []
    return list(dict.fromkeys(str(m).upper() for m in mods)) or ["TEXT"]


def _has_inline_media(body):
    """True if the request includes non-text media (image or audio) input."""
    for content in body.get("contents") or []:
        for part in content.get("parts") or []:
            if any(key in part for key in ("inlineData", "inline_data", "fileData", "file_data")):
                return True
    return False


def _multimodal_response(body):
    """Build a response whose usage metadata reflects the request's input/output modalities."""
    prompt_details = [{"modality": "TEXT", "tokenCount": 25}]
    prompt_details += [{"modality": m, "tokenCount": c} for m, c in _request_media_modalities(body).items()]
    prompt_total = sum(d["tokenCount"] for d in prompt_details)

    # A portion of each input modality is served from the context cache, so the
    # cache breakdown mirrors the prompt modalities (cached tokens are a subset
    # of the prompt total).
    cache_details = [{"modality": d["modality"], "tokenCount": d["tokenCount"] // 2} for d in prompt_details]
    cache_total = sum(d["tokenCount"] for d in cache_details)

    out_mods = _response_modalities(body)
    candidate_details = [{"modality": m, "tokenCount": _OUTPUT_MODALITY.get(m, 12)} for m in out_mods]
    candidate_total = sum(d["tokenCount"] for d in candidate_details)

    parts = []
    for m in out_mods:
        if m == "TEXT":
            parts.append({"text": "The attached media shows a mock scene."})
        elif m == "IMAGE":
            parts.append({"inlineData": {"mimeType": "image/png", "data": "bW9jaw=="}})
        elif m == "AUDIO":
            parts.append({"inlineData": {"mimeType": "audio/wav", "data": "bW9jaw=="}})
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": parts},
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "usageMetadata": {
            "promptTokenCount": prompt_total,
            "cachedContentTokenCount": cache_total,
            "candidatesTokenCount": candidate_total,
            "totalTokenCount": prompt_total + candidate_total,
            "promptTokensDetails": prompt_details,
            "cacheTokensDetails": cache_details,
            "candidatesTokensDetails": candidate_details,
        },
        "modelVersion": "gemini-2.0-flash",
        "responseId": "resp-mock-001",
    }


def _structured_response(body):
    """Answer a responseSchema request with a value that schema accepts."""
    config = body.get("generationConfig") or body.get("generation_config") or {}
    schema = config.get("responseSchema") or config.get("response_schema")
    response = copy.deepcopy(RESPONSE)
    answer = mock_json_schema_value(_json_schema(schema)) if schema else {}
    response["candidates"][0]["content"]["parts"] = [
        {"text": json.dumps(answer)}
    ]
    return response


# Gemini spells its schema in the protobuf enum names, upper case, so a
# generator written against JSON Schema needs them lowered first.
def _json_schema(schema):
    if isinstance(schema, list):
        return [_json_schema(entry) for entry in schema]
    if not isinstance(schema, dict):
        return schema
    lowered = {}
    for key, value in schema.items():
        if key in ("type", "type_") and isinstance(value, str):
            lowered["type"] = value.lower()
        else:
            lowered[key] = _json_schema(value)
    return lowered


def _wants_json(body):
    config = body.get("generationConfig") or body.get("generation_config") or {}
    mime = config.get("responseMimeType") or config.get("response_mime_type")
    return mime == "application/json"


def _batch_embedding_response(body):
    """One embedding per request entry: a client indexes them positionally."""
    requests = body.get("requests") or []
    response = copy.deepcopy(BATCH_EMBEDDING_RESPONSE)
    count = max(1, len(requests))
    response["embeddings"] = [
        {"values": [0.001] * 256} for _ in range(count)
    ]
    response["usageMetadata"] = {"promptTokenCount": 8 * count}
    return response


def _has_function_response(body):
    contents = body.get("contents") or []
    for content in contents:
        for part in content.get("parts") or []:
            if "functionResponse" in part or "function_response" in part:
                return True
    return False


def _function_call_part(body):
    declaration = next(
        (
            declaration
            for tool in body.get("tools") or []
            for declaration in (tool or {}).get("functionDeclarations")
            or (tool or {}).get("function_declarations")
            or []
        ),
        None,
    )
    if declaration is None:
        return None
    part = copy.deepcopy(FUNCTION_CALL_RESPONSE["candidates"][0]["content"]["parts"][0])
    if declaration.get("name"):
        part["functionCall"]["name"] = declaration["name"]
    # Newer google-genai/ADK send the schema as JSON Schema under
    # `parameters_json_schema` (a.k.a. `parametersJsonSchema`) instead of `parameters`.
    parameters = (
        declaration.get("parameters")
        or declaration.get("parameters_json_schema")
        or declaration.get("parametersJsonSchema")
        or {}
    )
    part["functionCall"]["args"] = mock_tool_arguments(
        {"function": {"parameters": parameters}}
    )
    return part


def _google_search_response(body):
    resp = copy.deepcopy(RESPONSE)
    resp["responseId"] = "response-search-1"
    candidate = resp["candidates"][0]
    # With tool combination the model searches, then asks for the function.
    parts = [
        _function_call_part(body)
        or {"text": "OpenTelemetry is an observability framework."}
    ]
    tool_config = body.get("toolConfig") or body.get("tool_config") or {}
    # Gemini returns the server-side call and result as parts only on opt-in.
    if tool_config.get("includeServerSideToolInvocations") or tool_config.get(
        "include_server_side_tool_invocations"
    ):
        parts = [
            {
                "toolCall": {
                    "id": "search-1",
                    "toolType": "GOOGLE_SEARCH_WEB",
                    "args": {"queries": ["OpenTelemetry"]},
                }
            },
            {
                "toolResponse": {
                    "id": "search-1",
                    "toolType": "GOOGLE_SEARCH_WEB",
                    "response": {
                        "results": [
                            {"title": "OpenTelemetry", "url": "https://opentelemetry.io/"}
                        ]
                    },
                }
            },
            *parts,
        ]
    candidate["content"]["parts"] = parts
    candidate["groundingMetadata"] = {
        "webSearchQueries": ["OpenTelemetry"],
        "groundingChunks": [
            {"web": {"uri": "https://opentelemetry.io/", "title": "OpenTelemetry"}}
        ],
    }
    return resp


def _tool_response(body):
    if any(
        "codeExecution" in tool or "code_execution" in tool
        for tool in body.get("tools") or []
    ):
        resp = copy.deepcopy(RESPONSE)
        resp["responseId"] = "response-code-1"
        resp["candidates"][0]["content"]["parts"] = [
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
        return resp
    if any(
        "googleSearch" in tool or "google_search" in tool
        for tool in body.get("tools") or []
    ):
        return _google_search_response(body)
    resp = copy.deepcopy(FUNCTION_CALL_RESPONSE)
    part = _function_call_part(body)
    if part:
        resp["candidates"][0]["content"]["parts"][0] = part
    return resp


def _stream_chunks():
    """Return the list of streaming chunks for Google GenAI / Vertex AI."""
    chunks = []
    for word in ["This ", "is ", "a ", "mock ", "streamed ", "response."]:
        chunks.append(
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": word}]},
                        "index": 0,
                    }
                ],
            }
        )
    chunks.append(
        {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": ""}]},
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 25,
                "candidatesTokenCount": 6,
                "totalTokenCount": 31,
            },
        }
    )
    return chunks


def _stream_ndjson():
    """Yield line-delimited JSON chunks for Google GenAI streaming."""
    for chunk in _stream_chunks():
        yield json.dumps(chunk) + "\n"


def _stream_json_array():
    """Yield a JSON array of chunks for Vertex AI REST streaming.

    The Vertex AI gapic REST transport expects the streaming response body
    to be a JSON array (``[{chunk}, {chunk}, ...]``), not NDJSON.
    """
    chunks = _stream_chunks()
    yield "["
    for i, chunk in enumerate(chunks):
        if i > 0:
            yield ","
        yield json.dumps(chunk)
    yield "]"


def _stream_sse():
    """Yield SSE-formatted chunks for Vertex AI JS SDK streaming.

    The JS ``@google-cloud/vertexai`` SDK requests ``?alt=sse`` and expects
    ``data: <json>\\n\\n`` framing.
    """
    for chunk in _stream_chunks():
        yield f"data: {json.dumps(chunk)}\n\n"


@bp.route("/v1beta/models/<path:model_action>", methods=["POST"])
def google_genai(model_action):
    """Handle Google GenAI API requests (generateContent, streamGenerateContent, embedContent)."""
    body = request.get_json(silent=True) or {}
    if ":streamGenerateContent" in model_action:
        return Response(_stream_ndjson(), mimetype="application/x-ndjson")
    if ":batchEmbedContents" in model_action:
        return _batch_embedding_response(body)
    if ":embedContent" in model_action:
        return EMBEDDING_RESPONSE
    # :generateContent or any other action
    if _has_function_response(body):
        return FUNCTION_RESPONSE
    if body.get("tools"):
        return _tool_response(body)
    if _has_inline_media(body) or set(_response_modalities(body)) != {"TEXT"}:
        return _multimodal_response(body)
    if _wants_json(body):
        return _structured_response(body)
    return RESPONSE


@bp.route("/v1beta/agents", methods=["POST"])
def google_genai_agents():
    """Handle Google GenAI Agents API requests."""
    body = request.get_json(silent=True) or {}
    return {
        "name": f"agents/{body.get('name', 'mock-agent-123')}",
        "displayName": body.get("display_name", "test-agent"),
    }


@bp.route("/v1beta/interactions", methods=["POST"])
def google_genai_interactions():
    """Handle Google GenAI Interactions API requests."""
    body = request.get_json(silent=True) or {}
    resp = _interaction_response(
        "interaction-mock-123",
        body.get("model", "gemini-2.0-flash"),
        body.get("previous_interaction_id"),
    )
    if any(tool.get("type") == "google_search" for tool in body.get("tools") or []):
        resp["steps"] = [
            {
                "type": "google_search_call",
                "id": "search-1",
                "arguments": {"queries": ["OpenTelemetry"]},
                "search_type": "web_search",
            },
            {
                "type": "google_search_result",
                "call_id": "search-1",
                "result": [],
                "is_error": False,
            },
            *resp["steps"],
        ]
    return resp


@bp.route("/v1beta/interactions/<interaction_id>", methods=["GET"])
def google_genai_get_interaction(interaction_id: str) -> dict[str, object]:
    """Return a completed interaction without requiring a preceding create."""
    return _interaction_response(interaction_id, "gemini-2.0-flash")


def _interaction_response(
    interaction_id: str, model: str, previous_interaction_id: str | None = None
) -> dict[str, object]:
    return {
        "id": interaction_id,
        "model": model,
        "status": "completed",
        "previous_interaction_id": previous_interaction_id,
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": "This is a response from the mock interactions server.",
                    }
                ],
            }
        ],
        "usage": {
            "total_tokens": 20,
            "total_input_tokens": 12,
            "total_output_tokens": 8,
            "total_cached_tokens": 0,
            "total_thought_tokens": 0,
        },
    }


@bp.route("/v1/projects/<path:rest>", methods=["POST"])
@bp.route("/v1beta1/projects/<path:rest>", methods=["POST"])
def vertex_ai(rest):
    """Handle Vertex AI API requests (same response format as Google GenAI)."""
    body = request.get_json(silent=True) or {}
    if ":streamGenerateContent" in rest:
        if request.args.get("alt") == "sse":
            return Response(_stream_sse(), mimetype="text/event-stream")
        return Response(_stream_json_array(), mimetype="application/json")
    if ":predict" in rest:
        # Vertex AI embeddings use the predict endpoint
        body = request.get_json(silent=True) or {}
        instances = body.get("instances", [])
        predictions = []
        for _ in instances:
            predictions.append({"embeddings": {"values": [0.001] * 256}})
        return {
            "predictions": predictions,
            "metadata": {"billableCharacterCount": 13},
        }
    if _has_function_response(body):
        return FUNCTION_RESPONSE
    if body.get("tools"):
        return _tool_response(body)
    if _has_inline_media(body) or set(_response_modalities(body)) != {"TEXT"}:
        return _multimodal_response(body)
    if _wants_json(body):
        return _structured_response(body)
    return RESPONSE
