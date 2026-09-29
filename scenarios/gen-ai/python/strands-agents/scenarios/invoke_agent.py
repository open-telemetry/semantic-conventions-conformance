# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Strands agent run.

Shared by every implementation under ``strands-agents/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing. Strands' own spans go to
whatever tracer provider the process has installed.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

from strands import Agent
from strands.models.openai import OpenAIModel

agent = Agent(
    name="weather_assistant",
    model=OpenAIModel(
        model_id="gpt-4o-mini",
        params={"max_tokens": 100, "temperature": 0.5},
    ),
    system_prompt="You are a helpful assistant.",
)

agent("Say this is a test")
