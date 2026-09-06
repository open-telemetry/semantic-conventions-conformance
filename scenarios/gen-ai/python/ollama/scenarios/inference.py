# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Ollama chat.

Shared by every implementation under ``ollama/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The request carries every sampling option the conventions have an attribute
for and the API accepts. Ollama takes them under ``options`` rather than as
top-level fields, and calls the token limit ``num_predict``.
"""

from ollama import chat

chat(
    model="llama3.2",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    options={
        "num_predict": 100,
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 40,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.2,
        "stop": ["\n\n"],
        "seed": 42,
    },
)
