# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Semantic Kernel agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio
from typing import Annotated

from openai import AsyncOpenAI
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
    service=OpenAIChatCompletion(
        ai_model_id="gpt-4o-mini", async_client=AsyncOpenAI()
    ),
    instructions="You are a helpful assistant.",
    plugins=[WeatherPlugin()],
    arguments=KernelArguments(
        settings=OpenAIChatPromptExecutionSettings(
            max_tokens=100, temperature=0.5
        ),
    ),
)

asyncio.run(
    agent.get_response(messages="What's the weather in Seattle today?")
)
