# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Groq chat completion.

Shared by every implementation under ``groq/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The request carries every sampling option the conventions have an attribute
for and the API accepts. Groq's chat completions API has no top-k.
"""

from groq import Groq

Groq().chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    seed=42,
)
