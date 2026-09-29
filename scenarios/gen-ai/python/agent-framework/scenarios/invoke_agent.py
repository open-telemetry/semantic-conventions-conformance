# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Agent Framework agent run.

Shared by every implementation under ``agent-framework/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing. The framework's own telemetry
is on by default and reads the environment for the rest.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

import asyncio

from agent_framework.openai import OpenAIChatCompletionClient

agent = OpenAIChatCompletionClient(model="gpt-4o-mini").as_agent(
    name="weather_assistant",
    instructions="You are a helpful assistant.",
    default_options={"max_tokens": 100, "temperature": 0.5},
)

asyncio.run(agent.run("Say this is a test"))
