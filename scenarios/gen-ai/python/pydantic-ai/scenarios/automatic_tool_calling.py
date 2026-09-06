# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Pydantic AI agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.settings import ModelSettings

agent = Agent(
    OpenAIChatModel("gpt-4o-mini"),
    name="weather_assistant",
    system_prompt="You are a helpful assistant.",
    model_settings=ModelSettings(max_tokens=100, temperature=0.5),
)


@agent.tool_plain
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


def run() -> None:
    agent.run_sync("What's the weather in Seattle today?")


if __name__ == "__main__":
    run()
