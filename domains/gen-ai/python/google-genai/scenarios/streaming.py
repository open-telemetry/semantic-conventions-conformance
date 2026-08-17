# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed google-genai generate_content call.

Same request as inference.py, delivered as a stream, consumed to the end so
the instrumentation sees the final chunk and its usage.
"""

from google import genai
from google.genai import types

client = genai.Client()

stream = client.models.generate_content_stream(
    model="gemini-2.0-flash",
    contents="Say this is a test",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        max_output_tokens=100,
        temperature=0.5,
        top_p=0.9,
        top_k=10,
        frequency_penalty=0.1,
        presence_penalty=0.2,
        stop_sequences=["\n\n"],
        seed=42,
    ),
)

for _ in stream:
    pass
