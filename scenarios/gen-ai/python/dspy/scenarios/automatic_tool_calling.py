# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a dspy agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import dspy


def get_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"70 degrees and sunny in {location}"


dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", temperature=0.5, max_tokens=100, cache=False))

agent = dspy.ReAct("question -> answer", tools=[get_weather])
agent(question="What's the weather in Seattle today?")
