# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Anthropic message, through langchain.

The same exchange as anthropic/scenarios/inference.py, made through
ChatAnthropic instead of the anthropic client, so the two data.json files
compare directly. Nothing here turns instrumentation on, and nothing here may.
"""

from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    top_k=10,
    stop=["\n\n"],
)

model.invoke(
    [
        ("system", "You are a helpful assistant."),
        ("human", "Say this is a test"),
    ]
)
