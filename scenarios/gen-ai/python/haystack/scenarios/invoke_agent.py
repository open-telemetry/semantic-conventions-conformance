# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single Haystack agent run.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own. The agent runs
inside a pipeline, which is how Haystack drives one.
"""

from haystack import Pipeline
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage

pipeline = Pipeline()
pipeline.add_component(
    "weather_assistant",
    Agent(
        chat_generator=OpenAIChatGenerator(
            model="gpt-4o-mini",
            generation_kwargs={"max_tokens": 100, "temperature": 0.5},
        ),
        system_prompt="You are a helpful assistant.",
    ),
)

def run() -> None:
    pipeline.run(
        {
            "weather_assistant": {
                "messages": [ChatMessage.from_user("Say this is a test")]
            }
        }
    )


if __name__ == "__main__":
    run()
