# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Mistral chat completion carrying an image.

One exchange, because an image is the only non-text content the chat API
takes: Mistral has no audio input or output on this route. Coverage records
attribute names only, so what this scenario is really checking is the *shape*
of the recorded content: whether the message parts an instrumentation writes
into ``gen_ai.input.messages`` validate against the registry schemas.
"""

import os

from mistralai.client import Mistral

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL")).chat.complete(
    model="pixtral-12b-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image_url", "image_url": IMAGE},
            ],
        },
    ],
    max_tokens=100,
    temperature=0.5,
)
