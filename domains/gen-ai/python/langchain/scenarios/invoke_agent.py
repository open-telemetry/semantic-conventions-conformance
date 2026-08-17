# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single langchain agent run.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=100),
    tools=[],
    system_prompt="You are a helpful assistant.",
    name="weather_assistant",
)

agent.invoke({"messages": [{"role": "user", "content": "Say this is a test"}]})
