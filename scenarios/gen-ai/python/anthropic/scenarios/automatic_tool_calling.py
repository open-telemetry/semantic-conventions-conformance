# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: anthropic automatic tool calling.

``beta.messages.tool_runner`` runs the tool itself and sends the result back,
so one call from the scenario is two model calls and one tool execution.
tool_calling.py is the same exchange driven by hand.

``tool_runner`` calls the model through ``client.beta.messages``. An
instrumentation that wraps only ``Messages.create``/``stream``/``parse``
emits nothing for this scenario; one that also wraps the beta methods does.
Which of those happens is what this scenario measures.
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
    extra_body={"temperature": 0.5},
)

for _ in runner:
    pass
