# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: anthropic automatic tool calling.

``beta.messages.tool_runner`` runs the tool itself and sends the result back,
so one call from the scenario is two model calls and one tool execution.
tool_calling.py is the same exchange driven by hand.

This scenario contributes nothing to the directory's coverage today, and that
is the finding: the instrumentation wraps ``Messages.create``/``stream``/
``parse``, and the beta namespace is a different class, so a tool_runner run
emits no telemetry at all.
"""

from anthropic import Anthropic, beta_tool


@beta_tool
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location.

    Args:
        location: The city and state, e.g. Boston, MA
    """
    return f"70 degrees and sunny in {location}"


runner = Anthropic().beta.messages.tool_runner(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "What's the weather in Seattle today?"}
    ],
    tools=[get_current_weather],
    max_tokens=100,
    temperature=0.5,
)

for _ in runner:
    pass
