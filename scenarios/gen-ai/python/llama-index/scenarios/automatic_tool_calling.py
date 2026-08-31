# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a LlamaIndex agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = FunctionAgent(
    name="weather_assistant",
    description="Answers questions about the weather",
    system_prompt="You are a helpful assistant.",
    llm=OpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=100),
    tools=[get_current_weather],
)

async def main() -> None:
    await agent.run("What's the weather in Seattle today?")


asyncio.run(main())
