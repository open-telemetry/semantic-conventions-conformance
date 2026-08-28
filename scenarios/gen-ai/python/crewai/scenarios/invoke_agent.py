# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single CrewAI agent run.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own. A crew of one
agent with one task is the smallest run CrewAI has.
"""

from crewai import LLM, Agent, Crew, Task

agent = Agent(
    role="weather_assistant",
    goal="Answer the question you are given",
    backstory="You are a helpful assistant.",
    llm=LLM(model="openai/gpt-4o-mini", temperature=0.5, max_tokens=100),
)

Crew(
    agents=[agent],
    tasks=[Task(description="Say this is a test", expected_output="A short reply", agent=agent)],
).kickoff()
