# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Anthropic message, through langchain.

Same request as inference.py, consumed to the end.
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

for _ in model.stream(
    [
        ("system", "You are a helpful assistant."),
        ("human", "Say this is a test"),
    ]
):
    pass
