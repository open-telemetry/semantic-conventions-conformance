# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a CrewAI agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

from crewai import LLM, Agent, Crew, Task
from crewai.tools import tool


@tool("get_current_weather")
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


agent = Agent(
    role="weather_assistant",
    goal="Answer the question you are given",
    backstory="You are a helpful assistant.",
    llm=LLM(model="openai/gpt-4o-mini", temperature=0.5, max_tokens=100),
    tools=[get_current_weather],
)

Crew(
    agents=[agent],
    tasks=[
        Task(
            description="What's the weather in Seattle today?",
            expected_output="A short reply",
            agent=agent,
        )
    ],
).kickoff()
