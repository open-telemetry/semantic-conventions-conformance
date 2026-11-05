# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: google-genai with hosted Google Search.

Gemini runs the search itself. include_server_side_tool_invocations asks it
to return the call and its result as toolCall and toolResponse parts beside
the answer; without it only grounding metadata comes back.
"""

from google import genai
from google.genai import types

client = genai.Client()
client.models.generate_content(
    model="gemini-3.8-flash",
    contents="What is OpenTelemetry?",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        tools=[types.Tool(google_search=types.GoogleSearch())],
        tool_config=types.ToolConfig(include_server_side_tool_invocations=True),
        max_output_tokens=100,
        temperature=0.5,
    ),
)
