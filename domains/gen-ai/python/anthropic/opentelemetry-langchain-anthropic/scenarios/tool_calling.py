# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Anthropic tool calling, through langchain.

Two round trips driven by hand, matching anthropic/scenarios/tool_calling.py.
langchain binds the tool as a schema and does not run it: the result is
built here, so no tool executes and no execute_tool span is emitted. Running
the tool is what automatic_tool_calling covers, in the agentic directory.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import ToolMessage

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

model = ChatAnthropic(
    model="claude-sonnet-4-20250514", max_tokens=100, temperature=0.5
)
with_tools = model.bind_tools([TOOL])

messages = [
    ("system", "You are a helpful assistant."),
    ("human", "What's the weather in Seattle today?"),
]

answer = with_tools.invoke(messages)
messages.append(answer)
for call in answer.tool_calls:
    messages.append(
        ToolMessage(
            content=f"70 degrees and sunny in {call['args']['location']}",
            tool_call_id=call["id"],
        )
    )

with_tools.invoke(messages)
