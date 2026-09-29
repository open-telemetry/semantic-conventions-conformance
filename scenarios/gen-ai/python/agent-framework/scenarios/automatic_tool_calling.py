# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an Agent Framework agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio
from typing import Annotated

from agent_framework.openai import OpenAIChatCompletionClient


def get_current_weather(
    location: Annotated[str, "The city and state, e.g. Boston, MA"],
) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = OpenAIChatCompletionClient(model="gpt-4o-mini").as_agent(
    name="weather_assistant",
    instructions="You are a helpful assistant.",
    tools=[get_current_weather],
    default_options={"max_tokens": 100, "temperature": 0.5},
)

asyncio.run(agent.run("What's the weather in Seattle today?"))
