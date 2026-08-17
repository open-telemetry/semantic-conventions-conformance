# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: google-genai function calling.

Two round trips, matching every other library's tool-calling scenario: the
tool declarations and the requested call, then the function response
travelling back as input. Automatic function calling is off, so the exchange
stays visible to the instrumentation as two model calls rather than one.
"""

from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"
TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_current_weather",
            description="Get the current weather in a given location",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "location": types.Schema(
                        type="STRING",
                        description="The city and state, e.g. Boston, MA",
                    ),
                },
                required=["location"],
            ),
        )
    ]
)
CONFIG = types.GenerateContentConfig(
    system_instruction="You are a helpful assistant.",
    tools=[TOOL],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        disable=True
    ),
    max_output_tokens=100,
    temperature=0.5,
)

client = genai.Client()
contents = [
    types.Content(
        role="user",
        parts=[types.Part(text="What's the weather in Seattle today?")],
    )
]

first = client.models.generate_content(
    model=MODEL, contents=contents, config=CONFIG
)

contents.append(first.candidates[0].content)
contents.append(
    types.Content(
        role="user",
        parts=[
            types.Part.from_function_response(
                name=call.name,
                response={
                    "weather": f"70 degrees and sunny in {call.args['location']}"
                },
            )
            for call in first.function_calls or []
        ],
    )
)

client.models.generate_content(model=MODEL, contents=contents, config=CONFIG)
