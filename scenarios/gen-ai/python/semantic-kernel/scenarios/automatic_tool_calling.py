# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Semantic Kernel agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio
from typing import Annotated

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import (
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.functions import KernelArguments, kernel_function


class WeatherPlugin:
    @kernel_function(
        description="Get the current weather in a given location."
    )
    def get_current_weather(
        self, location: Annotated[str, "The city name."]
    ) -> str:
        return f"70 degrees and sunny in {location}"


agent = ChatCompletionAgent(
    name="weather_assistant",
    service=OpenAIChatCompletion(ai_model_id="gpt-4o-mini"),
    instructions="You are a helpful assistant.",
    plugins=[WeatherPlugin()],
    arguments=KernelArguments(
        settings=OpenAIChatPromptExecutionSettings(
            max_tokens=100, temperature=0.5
        ),
    ),
)


def run() -> None:
    # By position: the agent's tracing reads the input messages only from the
    # positional arguments, and records an empty list for a keyword.
    asyncio.run(agent.get_response("What's the weather in Seattle today?"))


if __name__ == "__main__":
    run()
