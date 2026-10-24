# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: OpenAI hosted web search, through langchain.

Matches openai/scenarios/server_tool_calling.py. Binding a built-in tool
switches ChatOpenAI to the Responses API, and OpenAI runs the search itself.
"""

from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini", max_tokens=100, temperature=0.5)
model.bind_tools([{"type": "web_search"}]).invoke(
    [
        ("system", "You are a helpful assistant."),
        ("human", "What is OpenTelemetry?"),
    ]
)
