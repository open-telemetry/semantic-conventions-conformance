# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single AutoGen agent run.

Shared by every implementation under ``autogen/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing. AutoGen's own spans go to whatever
tracer provider the process has installed.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

agent = AssistantAgent(
    name="weather_assistant",
    model_client=OpenAIChatCompletionClient(
        model="gpt-4o-mini", max_tokens=100, temperature=0.5
    ),
    system_message="You are a helpful assistant.",
)

asyncio.run(agent.run(task="Say this is a test"))
