# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Anthropic hosted web search, through langchain.

Matches anthropic/scenarios/server_tool_calling.py. ChatAnthropic passes the
built-in tool through, and Anthropic runs the search itself.
"""

from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-sonnet-4-20250514", max_tokens=100, temperature=0.5
)
model.bind_tools(
    [{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}]
).invoke(
    [
        ("system", "You are a helpful assistant."),
        ("human", "What is OpenTelemetry?"),
    ]
)
