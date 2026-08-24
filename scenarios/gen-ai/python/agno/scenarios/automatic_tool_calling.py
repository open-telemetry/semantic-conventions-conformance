# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an agno agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

from agno.agent import Agent
from agno.models.openai import OpenAIChat


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = Agent(
    name="weather_assistant",
    model=OpenAIChat(id="gpt-4o-mini", temperature=0.5, max_tokens=100),
    instructions="You are a helpful assistant.",
    tools=[get_current_weather],
)

agent.run("What's the weather in Seattle today?")
