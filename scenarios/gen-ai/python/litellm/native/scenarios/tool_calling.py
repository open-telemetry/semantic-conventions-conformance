# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a litellm completion with tool calls.

Two round trips, because one is not enough: the first shows the tool
definitions and the call the model asks for, the second shows the tool result
travelling back as input. An instrumentation that only records one side of
that exchange is visible here and nowhere else.
"""

import json

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor

litellm.callbacks = ["otel"]

MODEL = "openai/gpt-4o-mini"
TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. Boston, MA",
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    },
}

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What's the weather in Seattle today?"},
]

first = litellm.completion(
    model=MODEL,
    messages=messages,
    tools=[TOOL],
    tool_choice="auto",
    max_tokens=100,
    temperature=0.5,
)

assistant_message = first.choices[0].message
messages.append(assistant_message.model_dump(exclude_none=True))
for tool_call in assistant_message.tool_calls or []:
    location = json.loads(tool_call.function.arguments)["location"]
    messages.append(
        {
            "role": "tool",
            "content": f"70 degrees and sunny in {location}",
            "tool_call_id": tool_call.id,
        }
    )

litellm.completion(
    model=MODEL,
    messages=messages,
    tools=[TOOL],
    max_tokens=100,
    temperature=0.5,
)

# LiteLLM runs its logging callbacks on a thread pool, so the span for the
# call above may not exist yet when this program returns. Waiting for that
# pool is what makes the run reproducible rather than a race with shutdown.
executor.shutdown(wait=True)
