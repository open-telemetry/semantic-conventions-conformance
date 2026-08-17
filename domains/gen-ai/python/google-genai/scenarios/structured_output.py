# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a google-genai call with a JSON schema answer.

Asking for a schema is what ``gen_ai.output.type`` describes, so the request
names one rather than only asking for "some JSON".
"""

from google import genai
from google.genai import types

client = genai.Client()

client.models.generate_content(
    model="gemini-2.0-flash",
    contents="What is the weather in Seattle?",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        response_mime_type="application/json",
        response_schema=types.Schema(
            type="OBJECT",
            properties={
                "location": types.Schema(type="STRING"),
                "temperature": types.Schema(type="INTEGER"),
                "conditions": types.Schema(
                    type="STRING", enum=["sunny", "cloudy", "rainy"]
                ),
            },
            required=["location", "temperature", "conditions"],
        ),
        max_output_tokens=100,
        temperature=0.5,
    ),
)
