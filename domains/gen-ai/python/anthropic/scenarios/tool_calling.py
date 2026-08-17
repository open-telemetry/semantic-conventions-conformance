# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an anthropic message with tool use.

Two round trips, matching every other library's tool-calling scenario: the
tool definitions and the requested call, then the tool result travelling back
as input.
"""

from anthropic import Anthropic

MODEL = "claude-sonnet-4-20250514"
TOOL = {
    "name": "get_current_weather",
    "description": "Get the current weather in a given location",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state, e.g. Boston, MA",
            },
        },
        "required": ["location"],
    },
}

client = Anthropic()
messages = [
    {"role": "user", "content": "What's the weather in Seattle today?"}
]

first = client.messages.create(
    model=MODEL,
    system="You are a helpful assistant.",
    messages=messages,
    tools=[TOOL],
    max_tokens=100,
    temperature=0.5,
)

messages.append({"role": "assistant", "content": first.content})
messages.append(
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"70 degrees and sunny in {block.input['location']}",
            }
            for block in first.content
            if block.type == "tool_use"
        ],
    }
)

client.messages.create(
    model=MODEL,
    system="You are a helpful assistant.",
    messages=messages,
    tools=[TOOL],
    max_tokens=100,
    temperature=0.5,
)
