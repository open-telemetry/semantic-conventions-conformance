# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single qwen-agent agent run.

No tools, so the run is the agent and the model call it makes. That is what
makes the agent span readable on its own. `Assistant` still runs its Memory
sub-agent, so a second agent span comes with it.

The `oai` model type is an OpenAI-compatible client, which is what lets the
run reach the mock server.
"""

from qwen_agent.agents import Assistant

agent = Assistant(
    llm={
        "model": "gpt-4o-mini",
        "model_type": "oai",
        "generate_cfg": {"temperature": 0.5, "max_tokens": 100},
    },
    name="weather_assistant",
    system_message="You are a helpful assistant.",
)

list(agent.run([{"role": "user", "content": "Say this is a test"}]))
