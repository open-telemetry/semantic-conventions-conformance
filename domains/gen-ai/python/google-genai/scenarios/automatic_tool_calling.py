# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: google-genai automatic function calling.

The SDK runs the tool itself and sends the result back, so one call from the
scenario is two model calls and one tool execution. tool_calling.py is the
same exchange driven by hand.
"""

from google import genai
from google.genai import types


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location.

    Args:
        location: The city and state, e.g. Boston, MA
    """
    return f"70 degrees and sunny in {location}"


client = genai.Client()

client.models.generate_content(
    model="gemini-2.0-flash",
    contents="What's the weather in Seattle today?",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        tools=[get_current_weather],
        max_output_tokens=100,
        temperature=0.5,
    ),
)
