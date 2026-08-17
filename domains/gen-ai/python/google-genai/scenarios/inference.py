# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain google-genai generate_content call.

Shared by every implementation under ``google-genai/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing.

The same exchange as every other library's inference scenario: a system
instruction and one user turn, carrying every sampling option the conventions
have an attribute for, under this SDK's names.
"""

from google import genai
from google.genai import types

client = genai.Client()

client.models.generate_content(
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
