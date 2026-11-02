# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Pydantic AI agent run.

Consume the response to the end so the instrumentation records token usage
and time to first chunk before the launcher flushes metrics.
"""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.settings import ModelSettings

agent = Agent(
    OpenAIChatModel("gpt-4o-mini"),
    name="weather_assistant",
    system_prompt="You are a helpful assistant.",
    model_settings=ModelSettings(
        max_tokens=100,
        temperature=0.5,
        top_p=0.9,
        frequency_penalty=0.1,
        presence_penalty=0.2,
        stop_sequences=["\n\n"],
        seed=42,
    ),
)


async def _run() -> None:
    async with agent.run_stream("Say this is a test") as result:
        async for _ in result.stream_text():
            pass


def run() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    run()
