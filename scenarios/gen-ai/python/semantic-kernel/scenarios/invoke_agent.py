# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Semantic Kernel agent run.

Shared by every implementation under ``semantic-kernel/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing. Semantic Kernel's own spans go
to whatever tracer provider the process has installed.

Semantic Kernel has no base-URL variable of its own, so the program hands it
an OpenAI client, which reads ``OPENAI_BASE_URL`` and ``OPENAI_API_KEY``.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
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

asyncio.run(agent.get_response(messages="Say this is a test"))
