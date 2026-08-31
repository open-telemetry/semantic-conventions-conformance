# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Groq chat completion carrying non-text content.

One exchange, for the one non-text content kind the chat API takes: an image,
on the way in. Groq's chat route has no audio input or output; audio goes
through the separate transcription API, which is not a chat completion.
Coverage records attribute names only, so what this scenario is really
checking is the *shape* of the recorded content: whether the message parts an
instrumentation writes into ``gen_ai.input.messages`` validate against the
registry schemas.
"""

from groq import Groq

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

Groq().chat.completions.create(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image_url", "image_url": {"url": IMAGE}},
            ],
        },
    ],
    max_tokens=100,
    temperature=0.5,
)
