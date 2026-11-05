# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a smolagents agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import os

from smolagents import OpenAIServerModel, ToolCallingAgent, tool


@tool
def get_weather(location: str) -> str:
    """Get the current weather in a given location.

    Args:
        location: The city to get the weather for.
    """
    return f"70 degrees and sunny in {location}"


model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_base=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0.5,
    max_tokens=100,
)

agent = ToolCallingAgent(
    name="weather_assistant",
    description="Answers questions about the weather.",
    tools=[get_weather],
    model=model,
    instructions="You are a helpful assistant.",
)

agent.run("What's the weather in Seattle today?")
