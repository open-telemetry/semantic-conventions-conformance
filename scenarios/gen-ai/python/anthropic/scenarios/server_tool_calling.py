# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an anthropic message with hosted web search.

Anthropic runs the search itself and returns the server_tool_use block and
its web_search_tool_result in the same response, so nothing runs on the
client and no execute_tool span is expected.
"""

from anthropic import Anthropic

Anthropic().messages.create(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "What is OpenTelemetry?"}],
    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}],
    max_tokens=100,
    extra_body={"temperature": 0.5},
)
