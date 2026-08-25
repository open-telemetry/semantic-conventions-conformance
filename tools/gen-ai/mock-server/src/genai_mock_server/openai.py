"""OpenAI-compatible chat / embeddings / responses endpoints."""

import copy
import json
import re

from flask import Blueprint, Response, request

from ._common import mock_json_schema_value, mock_tool_arguments, sse

bp = Blueprint("openai", __name__)

# Stored responses from `POST /v1/responses` with `store=True`, served back by
# `GET /v1/responses/{id}` so scenarios can fetch a previously generated
# response by its identifier.
_STORED_RESPONSES = {}

# Ids of responses created as background streams. Only these may be resumed via
# `GET /v1/responses/{id}?stream=true&starting_after=...`, mirroring OpenAI,
# which rejects cursor-based resumption of non-background/non-streaming responses.
_RESUMABLE_RESPONSES = set()


CHAT_REFUSAL_RESPONSE = {
    "id": "chatcmpl-mock-refusal-001",
    "object": "chat.completion",
    "service_tier": "default",
    "created": 1700000000,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "refusal": "I am unable to produce structured output for that request.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 30,
        "completion_tokens": 18,
        "total_tokens": 48,
    },
}


CHAT_RESPONSE = {
    "id": "chatcmpl-mock-001",
    "object": "chat.completion",
    "service_tier": "default",
    "created": 1700000000,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a response from the mock server.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 12,
        "total_tokens": 37,
    },
}

CHAT_TOOL_CALL_RESPONSE = {
    "id": "chatcmpl-mock-002",
    "object": "chat.completion",
    "service_tier": "default",
    "created": 1700000000,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_mock_001",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Seattle"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 20,
        "total_tokens": 70,
    },
}

CHAT_AUDIO_RESPONSE = {
    "id": "chatcmpl-mock-audio-001",
    "object": "chat.completion",
    "service_tier": "default",
    "created": 1700000000,
    "model": "gpt-4o-audio-preview",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a response from the mock server.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 40,
        # OpenAI breaks out audio (and cached) tokens within the prompt total.
        "prompt_tokens_details": {"audio_tokens": 0, "cached_tokens": 0},
        "completion_tokens": 20,
        "completion_tokens_details": {"audio_tokens": 0, "reasoning_tokens": 0},
        "total_tokens": 60,
    },
}

CHAT_AUDIO_MESSAGE_PART = {
    "id": "audio-mock-001",
    "expires_at": 1700003600,
    "data": "bW9jaw==",
    "transcript": "This is a response from the mock server.",
}

EMBEDDING_RESPONSE = {
    "id": "embd-mock-001",
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "index": 0,
            "embedding": [0.001] * 256,
        }
    ],
    "model": "text-embedding-3-small",
    "usage": {
        "prompt_tokens": 8,
        "total_tokens": 8,
    },
}

RESPONSES_RESPONSE = {
    "id": "resp-mock-001",
    "object": "response",
    "created_at": 1700000000,
    "status": "completed",
    "service_tier": "default",
    "model": "gpt-4o-mini",
    "output": [
        {
            "type": "message",
            "id": "msg-mock-001",
            "role": "assistant",
            "status": "completed",
            "content": [
                {
                    "type": "output_text",
                    "text": "This is a response from the mock server.",
                }
            ],
        }
    ],
    "usage": {
        "input_tokens": 25,
        "input_tokens_details": {
            "cached_tokens": 5,
            "cache_write_tokens": 8,
        },
        "output_tokens": 12,
        "output_tokens_details": {
            "reasoning_tokens": 3,
        },
        "total_tokens": 37,
    },
}


def _served_service_tier(body):
    """The tier the request is answered on.

    The real API reports the tier that actually served the request, so "auto"
    comes back as the tier it resolved to rather than as "auto".
    """
    requested = body.get("service_tier")
    if not requested or requested == "auto":
        return "default"
    return requested


def _has_audio_input(body):
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "input_audio":
                    return True
    return False


def _wants_audio_output(body):
    return "audio" in (body.get("modalities") or [])


def _chat_audio_response(body):
    """Report audio tokens on the side of the exchange that actually carries audio."""
    response = copy.deepcopy(CHAT_AUDIO_RESPONSE)
    usage = response["usage"]
    if _has_audio_input(body):
        usage["prompt_tokens_details"]["audio_tokens"] = 10
    if _wants_audio_output(body):
        usage["completion_tokens_details"]["audio_tokens"] = 15
        message = response["choices"][0]["message"]
        message["audio"] = copy.deepcopy(CHAT_AUDIO_MESSAGE_PART)
        message["content"] = None
    return response


def _responses_tool_call_response(body):
    response = copy.deepcopy(RESPONSES_RESPONSE)
    response["id"] = "resp-mock-tool-001"
    response["model"] = body.get("model", response["model"])
    tool = body.get("tools", [{}])[0]
    function = tool.get("function", {})
    tool_name = tool.get("name") or function.get("name")
    response["output"] = [
        {
            "type": "function_call",
            "id": "fc_mock_001",
            "call_id": "call_mock_001",
            "name": tool_name or "get_weather",
            "arguments": json.dumps(mock_tool_arguments(tool)),
            "status": "completed",
        }
    ]
    return response


def _mock_chat_content(body, message_text):
    # CrewAI converter retry, recognised by its schema-conversion system prompt
    # (crewai/translations/en.json, formatted_task_instructions): answer with a
    # PlannerTaskPydanticOutput-shaped body so the conversion succeeds.
    if "Format your final answer according to the following OpenAPI schema" in message_text:
        return json.dumps(
            {
                "list_of_plans_per_task": [
                    {
                        "task_number": 1,
                        "task": "task 1",
                        "plan": (
                            "Step 1: Identify the inputs required for task 1. "
                            "Step 2: Run the appropriate tool. "
                            "Step 3: Summarize the result."
                        ),
                    }
                ]
            }
        )

    # CrewAI CrewPlanner, recognised by the planning agent's role string. One
    # plan per "Task Number N -" marker the planner injects into the message.
    if "Task Execution Planner" in message_text:
        task_count = max(1, message_text.count("Task Number "))
        plans = [
            {
                "task_number": i + 1,
                "task": f"task {i + 1}",
                "plan": (
                    f"Step 1: Identify the inputs required for task {i + 1}. "
                    "Step 2: Run the appropriate tool. "
                    "Step 3: Summarize the result."
                ),
            }
            for i in range(task_count)
        ]
        return json.dumps({"list_of_plans_per_task": plans})

    # langchain-experimental Plan-and-Execute, recognised by the system prompt
    # load_chat_planner injects. PlanningOutputParser splits on "\n\d+\. ".
    if "<END_OF_PLAN>" in message_text:
        return (
            "Plan:\n"
            "1. Identify the inputs required to answer the question.\n"
            "2. Look up the relevant facts.\n"
            "3. Given the above steps taken, please respond to the users original question.\n"
            "<END_OF_PLAN>"
        )

    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        json_schema = response_format.get("json_schema") or {}
        return json.dumps(mock_json_schema_value(json_schema.get("schema")))
    if response_format.get("type") != "json_object":
        return "This is a response from the mock server."

    if "Relevance-Judge" in message_text or "Relevance Evaluator" in message_text:
        return json.dumps(
            {
                "explanation": "The response directly answers the user's question and stays fully on topic.",
                "score": 5,
            }
        )

    return json.dumps(
        {
            "explanation": "The response satisfies the evaluator request.",
            "score": 5,
        }
    )


def _text_protocol_tool_call(body, message_text):
    """Tool call for the Hermes/Nous text protocol, as qwen-agent drives it.

    Those clients advertise tools inside a ``<tools>`` block in the system
    prompt and expect the call back as ``<tool_call>`` JSON in the assistant
    content rather than through the ``tools`` request field.
    """
    if "<tools>" not in message_text or "<tool_call>" not in message_text:
        return None
    if "<tool_response>" in message_text or "<tool_call>" in "".join(
        message.get("content") or ""
        for message in body.get("messages", [])
        if message.get("role") == "assistant"
    ):
        return None

    tools = []
    # The instructions mention an empty <tools></tools> pair before the real
    # one, so every section is scanned rather than just the first.
    for section in re.findall(r"<tools>(.*?)</tools>", message_text, re.DOTALL):
        for line in section.strip().splitlines():
            try:
                tools.append(json.loads(line))
            except ValueError:
                pass
    if not tools:
        return None

    function = tools[0].get("function", tools[0])
    parameters = function.get("parameters")
    if isinstance(parameters, list):
        # These clients describe parameters as a list of named entries rather
        # than as a JSON Schema object.
        parameters = {
            "properties": {
                parameter["name"]: parameter for parameter in parameters
            },
            "required": [
                parameter["name"]
                for parameter in parameters
                if parameter.get("required")
            ],
        }
    arguments = mock_tool_arguments({"parameters": parameters or {}})
    return (
        "<tool_call>\n"
        + json.dumps({"name": function.get("name"), "arguments": arguments})
        + "\n</tool_call>"
    )


def _wants_tool_call(body):
    """Whether this request should be answered with a call to its first tool.

    Offered tools and no tool result yet, which is the same rule the
    non-streaming path follows so a framework sees the same exchange either
    way.
    """
    if not body.get("tools"):
        return False
    return not any(
        message.get("role") == "tool" for message in body.get("messages", [])
    )


def _stream_tool_call(body, model, chunk_id):
    """Yield the SSE chunks of a streamed tool call.

    The call arrives split across deltas, name first and arguments after, the
    way OpenAI sends one: a client that only reassembles the first delta is
    wrong in a way a single-chunk mock would hide.
    """
    tool = body.get("tools", [{}])[0]
    function = tool.get("function", tool)
    name = function.get("name") or "get_weather"
    arguments = json.dumps(mock_tool_arguments(tool))

    for delta in (
        {"id": "call_mock_001", "type": "function", "function": {"name": name, "arguments": ""}},
        {"function": {"arguments": arguments}},
    ):
        yield sse(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": 1700000000,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [{"index": 0, **delta}]},
                        "finish_reason": None,
                    }
                ],
            }
        )

    yield sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70,
            },
        }
    )

    yield "data: [DONE]\n\n"


def _stream_chat(body):
    """Yield SSE chunks for an OpenAI streaming chat completion."""
    model = body.get("model", "gpt-4o-mini")
    chunk_id = "chatcmpl-mock-stream-001"

    yield sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": model,
            "service_tier": _served_service_tier(body),
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
    )

    if _wants_tool_call(body):
        yield from _stream_tool_call(body, model, chunk_id)
        return

    message_text = "\n".join(
        message.get("content", "")
        for message in body.get("messages", [])
        if isinstance(message.get("content"), str)
    )
    content = _text_protocol_tool_call(body, message_text)
    words = (
        [content]
        if content
        else ["This ", "is ", "a ", "mock ", "streamed ", "response."]
    )
    for word in words:
        yield sse(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": 1700000000,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": word}, "finish_reason": None}],
            }
        )

    yield sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 6,
                "total_tokens": 31,
            },
        }
    )

    yield "data: [DONE]\n\n"


@bp.route("/v1/chat/completions", methods=["POST"])
@bp.route("/openai/v1/chat/completions", methods=["POST"])
@bp.route("/openai/deployments/<deployment>/chat/completions", methods=["POST"])
@bp.route("/chat/completions", methods=["POST"])
def chat_completions(deployment=None):
    body = request.get_json(silent=True) or {}

    if body.get("stream"):
        return Response(_stream_chat(body), mimetype="text/event-stream")

    message_text = "\n".join(
        message.get("content", "") for message in body.get("messages", []) if isinstance(message.get("content"), str)
    )

    # Offered tools but no tool result yet: call the tool, else answer.
    if body.get("tools"):
        messages = body.get("messages", [])
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if not has_tool_result:
            resp = copy.deepcopy(CHAT_TOOL_CALL_RESPONSE)
            resp["model"] = body.get("model", resp["model"])
            tool = body.get("tools", [{}])[0]
            tool_name = tool.get("function", {}).get("name")
            if tool_name:
                resp["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = tool_name
            resp["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps(
                mock_tool_arguments(tool)
            )
            resp["service_tier"] = _served_service_tier(body)
            return resp

    # CrewAI planner natural-retry path: a refusal, then a schema-invalid
    # answer, drives CrewAI through three LLM round-trips under one plan span.
    # The [FORCE_PLANNER_MULTI_CALL] sentinel keeps that to this scenario;
    # other crewai runs take the standard planner branch below.
    if (
        "[FORCE_PLANNER_MULTI_CALL]" in message_text
        and "Task Execution Planner" in message_text
        and body.get("response_format")
    ):
        # First call: beta.parse path -- return refusal so parsed_object=None
        # and CrewAI falls through to the regular create() path.
        resp = copy.deepcopy(CHAT_REFUSAL_RESPONSE)
        resp["model"] = body.get("model", resp["model"])
        resp["service_tier"] = _served_service_tier(body)
        return resp

    if (
        "[FORCE_PLANNER_MULTI_CALL]" in message_text
        and "Task Execution Planner" in message_text
        and not body.get("response_format")
    ):
        # Second call: fall-through create() with NO response_format. Return
        # text the converter will fail to validate as PlannerTaskPydanticOutput,
        # which forces convert_to_model -> handle_partial_json ->
        # convert_with_instructions and a third LLM round-trip.
        resp = copy.deepcopy(CHAT_RESPONSE)
        resp["model"] = body.get("model", resp["model"])
        resp["choices"][0]["message"]["content"] = "I drafted this plan but it is not in the requested schema."
        resp["service_tier"] = _served_service_tier(body)
        return resp

    # Audio input/output: OpenAI reports per-modality (audio) token counts in usage.
    if _has_audio_input(body) or _wants_audio_output(body):
        resp = _chat_audio_response(body)
        resp["model"] = body.get("model", resp["model"])
        resp["service_tier"] = _served_service_tier(body)
        return resp

    resp = copy.deepcopy(CHAT_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    resp["service_tier"] = _served_service_tier(body)
    resp["choices"][0]["message"]["content"] = _text_protocol_tool_call(
        body, message_text
    ) or _mock_chat_content(body, message_text)
    return resp


@bp.route("/v1/embeddings", methods=["POST"])
@bp.route("/openai/v1/embeddings", methods=["POST"])
@bp.route("/openai/deployments/<deployment>/embeddings", methods=["POST"])
@bp.route("/embeddings", methods=["POST"])
def embeddings(deployment=None):
    body = request.get_json(silent=True) or {}
    resp = copy.deepcopy(EMBEDDING_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    # Clients batch a list in one request and index the answers back onto it
    # positionally. A list of numbers is one input given as token ids.
    raw_input = body.get("input")
    if isinstance(raw_input, list) and all(
        isinstance(entry, (str, list)) for entry in raw_input
    ):
        count = len(raw_input)
    else:
        count = 1
    if not raw_input:
        return {
            "error": {
                "type": "invalid_request_error",
                "message": "'input' is a required property",
            }
        }, 400
    default_width = len(EMBEDDING_RESPONSE["data"][0]["embedding"])
    try:
        width = int(body.get("dimensions") or default_width)
    except (TypeError, ValueError):
        width = default_width
    vector = [0.001] * max(1, min(width, default_width * 16))
    resp["data"] = [
        {"object": "embedding", "index": index, "embedding": list(vector)}
        for index in range(count)
    ]
    resp["usage"] = {"prompt_tokens": 8 * count, "total_tokens": 8 * count}
    return resp


@bp.route("/v1/responses", methods=["POST"])
@bp.route("/openai/v1/responses", methods=["POST"])
def responses():
    body = request.get_json(silent=True) or {}
    raw_request_input = body.get("input")
    if isinstance(raw_request_input, list):
        request_input = [item for item in raw_request_input if isinstance(item, dict)]
    else:
        request_input = []
    # Call the first offered tool unless it has already been called in this
    # input. Keying on the offered tool rather than on the presence of any
    # function_call_output lets a multi-agent run still exercise the tool of
    # the agent it handed off to, whose own handoff already produced one.
    offered = {
        tool.get("name") or (tool.get("function") or {}).get("name")
        for tool in body.get("tools") or []
    }
    called = {
        item.get("name")
        for item in request_input
        if item.get("type") == "function_call"
    }
    if body.get("tools") and "agent_reference" not in body and not (offered & called):
        return _responses_tool_call_response(body)

    resp = copy.deepcopy(RESPONSES_RESPONSE)
    resp["model"] = body.get("model", resp["model"])
    if body.get("instructions") is not None:
        resp["instructions"] = body["instructions"]
    context_management = body.get("context_management") or []
    if any(item.get("type") == "compaction" for item in context_management if isinstance(item, dict)):
        resp["output"][0]["content"][0]["text"] = "Great question. Here is Jevons Paradox in simple terms."
        resp["output"].append(
            {
                "type": "compaction",
                "id": "cmp-mock-001",
                "encrypted_content": "opaque encrypted compaction state from a prior turn",
                "created_by": "server",
            },
        )
    if body.get("store"):
        _STORED_RESPONSES[resp["id"]] = copy.deepcopy(resp)
    if body.get("stream"):
        # Background streaming create: emit lifecycle events then end before
        # completion, as if the caller disconnected. Such a response can be
        # resumed later via `GET .../{id}?stream=true&starting_after=<seq>`.
        if body.get("background"):
            _RESUMABLE_RESPONSES.add(resp["id"])
            return Response(_stream_create(resp), mimetype="text/event-stream")
        return Response(_stream_response(resp), mimetype="text/event-stream")
    return resp


def _stream_response(response):
    """Yield the SSE lifecycle of a streaming response that runs to completion."""
    in_progress = copy.deepcopy(response)
    in_progress["status"] = "in_progress"
    in_progress["output"] = []
    in_progress["usage"] = None
    yield sse({"type": "response.created", "sequence_number": 0, "response": in_progress})
    yield sse({"type": "response.in_progress", "sequence_number": 1, "response": in_progress})

    item = copy.deepcopy(response["output"][0])
    sequence = 2
    if item.get("type") == "message":
        added = copy.deepcopy(item)
        added["status"] = "in_progress"
        added["content"] = []
        yield sse(
            {
                "type": "response.output_item.added",
                "sequence_number": sequence,
                "output_index": 0,
                "item": added,
            }
        )
        sequence += 1
        yield sse(
            {
                "type": "response.content_part.added",
                "sequence_number": sequence,
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            }
        )
        sequence += 1
        text = item["content"][0]["text"]
        for word in text.split(" "):
            yield sse(
                {
                    "type": "response.output_text.delta",
                    "sequence_number": sequence,
                    "item_id": item["id"],
                    "output_index": 0,
                    "content_index": 0,
                    "delta": word + " ",
                }
            )
            sequence += 1
        yield sse(
            {
                "type": "response.output_text.done",
                "sequence_number": sequence,
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "text": text,
            }
        )
        sequence += 1
        yield sse(
            {
                "type": "response.content_part.done",
                "sequence_number": sequence,
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": text, "annotations": []},
            }
        )
        sequence += 1
    yield sse(
        {
            "type": "response.output_item.done",
            "sequence_number": sequence,
            "output_index": 0,
            "item": item,
        }
    )
    sequence += 1
    yield sse({"type": "response.completed", "sequence_number": sequence, "response": response})


def _stream_create(response):
    """Yield SSE lifecycle events for a background streaming create.

    Ends after `response.in_progress` (before completion), modelling a caller
    that disconnects mid-stream and later resumes the response by cursor.
    """
    in_progress = copy.deepcopy(response)
    in_progress["status"] = "in_progress"
    in_progress["output"] = []
    in_progress["usage"] = None
    yield sse({"type": "response.created", "sequence_number": 0, "response": in_progress})
    yield sse({"type": "response.in_progress", "sequence_number": 1, "response": in_progress})


@bp.route("/v1/responses/<response_id>", methods=["GET"])
@bp.route("/openai/v1/responses/<response_id>", methods=["GET"])
def retrieve_response(response_id):
    # A `failed`-prefixed id lets scenarios fetch a response whose original
    # generation failed, so the fetch_response instrumentation can be exercised
    # against a non-completed status.
    if response_id.startswith("resp-failed"):
        failed = copy.deepcopy(RESPONSES_RESPONSE)
        failed["id"] = response_id
        failed["status"] = "failed"
        failed["output"] = []
        failed["usage"] = None
        failed["error"] = {
            "code": "server_error",
            "message": "The model failed to generate a response.",
        }
        return dict(failed)
    stored = _STORED_RESPONSES.get(response_id)
    if stored is None:
        stored = copy.deepcopy(RESPONSES_RESPONSE)
        stored["id"] = response_id
    # A streaming retrieve resumes the response stream from `starting_after`,
    # OpenAI's cursor for the last event the caller already received. Only
    # background streaming responses are resumable; reject cursor retrieval of
    # any other response, as OpenAI does. Emit the terminal `response.completed`
    # event carrying the full response object.
    if request.args.get("stream", "").lower() in ("1", "true"):
        if response_id not in _RESUMABLE_RESPONSES:
            return {
                "error": {
                    "type": "invalid_request_error",
                    "message": "Only background responses created with streaming can be resumed.",
                }
            }, 400
        starting_after = request.args.get("starting_after")
        return Response(_stream_retrieve(stored, starting_after), mimetype="text/event-stream")
    return dict(stored)


def _stream_retrieve(response, starting_after):
    """Yield SSE events resuming a stored response stream after `starting_after`."""
    sequence_number = int(starting_after) + 1 if starting_after is not None else 0
    yield sse(
        {
            "type": "response.completed",
            "sequence_number": sequence_number,
            "response": response,
        }
    )
