# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an Ollama chat with tool calls.

Two round trips, because one is not enough: the first shows the tool
definitions and the call the model asks for, the second shows the tool result
travelling back as input. An instrumentation that only records one side of
that exchange is visible here and nowhere else.
"""

from ollama import chat

MODEL = "llama3.2"
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
        },
    },
}
OPTIONS = {"num_predict": 100, "temperature": 0.5}

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What's the weather in Seattle today?"},
]

first = chat(model=MODEL, messages=messages, tools=[TOOL], options=OPTIONS)

messages.append(first.message)
for tool_call in first.message.tool_calls or []:
    location = tool_call.function.arguments["location"]
    messages.append(
        {
            "role": "tool",
            "tool_name": tool_call.function.name,
            "content": f"70 degrees and sunny in {location}",
        }
    )

chat(model=MODEL, messages=messages, tools=[TOOL], options=OPTIONS)
