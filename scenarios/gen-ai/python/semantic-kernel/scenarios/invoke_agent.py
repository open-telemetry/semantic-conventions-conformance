# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Semantic Kernel agent run.

Shared by every implementation under ``semantic-kernel/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing. Semantic Kernel's own spans go
to whatever tracer provider the process has installed.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

import asyncio

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import (
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.functions import KernelArguments

agent = ChatCompletionAgent(
    name="weather_assistant",
    service=OpenAIChatCompletion(ai_model_id="gpt-4o-mini"),
    instructions="You are a helpful assistant.",
    arguments=KernelArguments(
        settings=OpenAIChatPromptExecutionSettings(
            max_tokens=100, temperature=0.5
        ),
    ),
)


def run() -> None:
    asyncio.run(agent.get_response("Say this is a test"))


if __name__ == "__main__":
    run()
