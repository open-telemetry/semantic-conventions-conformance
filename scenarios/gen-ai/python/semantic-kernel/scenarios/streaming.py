# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Semantic Kernel agent run.

The same run as invoke_agent.py, with the same sampling options, through ``invoke_stream`` and consumed to the
last update so the instrumentation sees the final message, its usage and the time to the first chunk.
"""

import asyncio

from openai import AsyncOpenAI
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import (
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.functions import KernelArguments

agent = ChatCompletionAgent(
    name="weather_assistant",
    service=OpenAIChatCompletion(
        ai_model_id="gpt-4o-mini", async_client=AsyncOpenAI()
    ),
    instructions="You are a helpful assistant.",
    arguments=KernelArguments(
        settings=OpenAIChatPromptExecutionSettings(
            max_tokens=100,
            temperature=0.5,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.2,
            stop=["\n\n"],
            seed=42,
        ),
    ),
)


async def _run() -> None:
    async for _ in agent.invoke_stream(messages="Say this is a test"):
        pass


asyncio.run(_run())
