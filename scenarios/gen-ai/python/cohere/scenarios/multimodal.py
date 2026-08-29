# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Cohere chat carrying non-text content.

One exchange, for the one non-text content kind the chat API takes: an image,
on the way in. Cohere has no audio on this route. Coverage records attribute
names only, so what this scenario is really checking is the *shape* of the
recorded content: whether the message parts an instrumentation writes into
``gen_ai.input.messages`` validate against the registry schemas.
"""

import cohere

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

cohere.ClientV2().chat(
    model="command-a-vision-07-2025",
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
