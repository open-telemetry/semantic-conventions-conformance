# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Pydantic AI agent run.

Shared by every implementation under ``pydantic-ai/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
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

def run() -> None:
    agent.run_sync("Say this is a test")


if __name__ == "__main__":
    run()
