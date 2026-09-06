# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Cohere chat.

Shared by every implementation under ``cohere/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The request carries every sampling option the conventions have an attribute
for and the API accepts. Cohere calls top-p ``p`` and top-k ``k``.
"""

import cohere

cohere.ClientV2().chat(
    model="command-a-03-2025",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    p=0.9,
    k=40,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop_sequences=["\n\n"],
    seed=42,
)
