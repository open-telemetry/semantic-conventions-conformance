# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: openai chat completion with tool calls.

Shared by every implementation under ``openai/``; see inference.py.
"""

import json

from openai import OpenAI

MODEL = "gpt-4o-mini"
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

client = OpenAI()
messages = [
    {"role": "system", "content": "You're a helpful assistant."},
    {
        "role": "user",
        "content": "What's the weather in Seattle and San Francisco today?",
    },
]

first = client.chat.completions.create(
    messages=messages,
    model=MODEL,
    tool_choice="auto",
    tools=[TOOL],
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

client.chat.completions.create(messages=messages, model=MODEL)
