# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an Ollama chat carrying non-text content.

One exchange, for the one non-text content kind the chat API takes: an image,
on the way in. Ollama has no audio on this route, and carries images as a list
beside the text rather than as content parts. Coverage records attribute names
only, so what this scenario is really checking is the *shape* of the recorded
content: whether the message parts an instrumentation writes into
``gen_ai.input.messages`` validate against the registry schemas.
"""

from ollama import chat

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

chat(
    model="llama3.2-vision",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "What is in this image?",
            "images": [IMAGE],
        },
    ],
    options={"num_predict": 100, "temperature": 0.5},
)
