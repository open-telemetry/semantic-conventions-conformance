# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single agno agent run.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(
    name="weather_assistant",
    model=OpenAIChat(id="gpt-4o-mini", temperature=0.5, max_tokens=100),
    instructions="You are a helpful assistant.",
)

agent.run("Say this is a test")
