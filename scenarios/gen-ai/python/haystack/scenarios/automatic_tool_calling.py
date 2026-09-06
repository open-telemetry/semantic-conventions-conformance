# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Haystack agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

from haystack import Pipeline
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import Tool


def get_current_weather(location: str) -> str:
    return f"70 degrees and sunny in {location}"


WEATHER_TOOL = Tool(
    name="get_current_weather",
    description="Get the current weather in a given location",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state, e.g. Boston, MA",
            },
        },
        "required": ["location"],
    },
    function=get_current_weather,
)

pipeline = Pipeline()
pipeline.add_component(
    "weather_assistant",
    Agent(
        chat_generator=OpenAIChatGenerator(
            model="gpt-4o-mini",
            generation_kwargs={"max_tokens": 100, "temperature": 0.5},
        ),
        system_prompt="You are a helpful assistant.",
        tools=[WEATHER_TOOL],
    ),
)


def run() -> None:
    pipeline.run(
        {
            "weather_assistant": {
                "messages": [
                    ChatMessage.from_user("What's the weather in Seattle today?")
                ]
            }
        }
    )


if __name__ == "__main__":
    run()
