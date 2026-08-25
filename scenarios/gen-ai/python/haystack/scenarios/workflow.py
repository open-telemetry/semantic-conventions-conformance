# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Haystack pipeline, with no agent around it.

Shared by every implementation under ``haystack/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

A prompt piped into a chat generator is the smallest thing Haystack calls a
pipeline, and a pipeline is what the conventions call a workflow. Kept free of
tools and agents so the workflow span stands on its own.
"""

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage

pipeline = Pipeline()
pipeline.add_component("prompt_builder", ChatPromptBuilder())
pipeline.add_component(
    "llm",
    OpenAIChatGenerator(
        model="gpt-4o-mini",
        generation_kwargs={"max_tokens": 100, "temperature": 0.5},
    ),
)
pipeline.connect("prompt_builder.prompt", "llm.messages")

def run() -> None:
    pipeline.run(
        {
            "prompt_builder": {
                "template": [
                    ChatMessage.from_system("You are a helpful assistant."),
                    ChatMessage.from_user("{{question}}"),
                ],
                "template_variables": {"question": "Say this is a test"},
            }
        }
    )


if __name__ == "__main__":
    run()
