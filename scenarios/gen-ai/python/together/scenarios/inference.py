# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Together chat completion.

Shared by every implementation under ``together/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The request carries every sampling option the conventions have an attribute
for and the API accepts. Together's chat completions API takes all of them.
"""

from together import Together

Together().chat.completions.create(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    top_k=40,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    seed=42,
)
