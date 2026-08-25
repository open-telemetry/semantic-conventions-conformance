# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an AutoGen agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = AssistantAgent(
    name="weather_assistant",
    model_client=OpenAIChatCompletionClient(
        model="gpt-4o-mini", max_tokens=100, temperature=0.5
    ),
    system_message="You are a helpful assistant.",
    tools=[get_current_weather],
)

asyncio.run(agent.run(task="What's the weather in Seattle today?"))
