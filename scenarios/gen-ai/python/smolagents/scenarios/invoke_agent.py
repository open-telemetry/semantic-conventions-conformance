# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single smolagents agent run.

No tools of the caller's, so the run is the agent, its model calls and the
built-in ``final_answer`` step and nothing else. That is what makes the agent
span readable on its own.
"""

import os

from smolagents import OpenAIServerModel, ToolCallingAgent

model = OpenAIServerModel(
    model_id="gpt-4o-mini",
    api_base=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0.5,
    max_tokens=100,
)

agent = ToolCallingAgent(
    name="weather_assistant",
    description="Answers questions about the weather.",
    tools=[],
    model=model,
    instructions="You are a helpful assistant.",
)

agent.run("Say this is a test")
