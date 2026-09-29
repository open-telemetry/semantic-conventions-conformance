# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Strands agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

from strands import Agent, tool
from strands.models.openai import OpenAIModel


@tool
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = Agent(
    name="weather_assistant",
    model=OpenAIModel(
        model_id="gpt-4o-mini",
        params={"max_tokens": 100, "temperature": 0.5},
    ),
    system_prompt="You are a helpful assistant.",
    tools=[get_current_weather],
)

agent("What's the weather in Seattle today?")
