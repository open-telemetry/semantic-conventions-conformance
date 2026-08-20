# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single openai-agents agent run.

Shared by every implementation under ``openai-agents/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing.

The Agents SDK wraps every run in a trace, so this covers the workflow around
the agent as well as the agent itself. The workflow is named explicitly rather
than left as the SDK default, so the name on the span is one this scenario
chose.
"""

from agents import Agent, ModelSettings, RunConfig, Runner

agent = Agent(
    name="weather_assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o-mini",
    model_settings=ModelSettings(
        max_tokens=100,
        temperature=0.5,
        top_p=0.9,
        frequency_penalty=0.1,
        presence_penalty=0.2,
    ),
)

Runner.run_sync(
    agent,
    "Say this is a test",
    run_config=RunConfig(workflow_name="conformance_workflow"),
)
