# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an openai response with hosted web search.

Hosted tools exist only on the Responses API, so this is the one openai
program that does not use chat completions. OpenAI runs the search and
returns the web_search_call item beside the answer, so nothing runs on the
client and no execute_tool span is expected.
"""

from openai import OpenAI

OpenAI().responses.create(
    model="gpt-4o-mini",
    instructions="You are a helpful assistant.",
    input="What is OpenTelemetry?",
    tools=[{"type": "web_search"}],
    max_output_tokens=100,
    temperature=0.5,
)
