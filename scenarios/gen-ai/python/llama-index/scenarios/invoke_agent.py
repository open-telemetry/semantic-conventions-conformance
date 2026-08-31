# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single LlamaIndex agent run.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

import asyncio

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

agent = FunctionAgent(
    name="weather_assistant",
    description="Answers the question it is given",
    system_prompt="You are a helpful assistant.",
    llm=OpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=100),
)

async def main() -> None:
    await agent.run("Say this is a test")


asyncio.run(main())
