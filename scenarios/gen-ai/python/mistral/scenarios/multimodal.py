# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Mistral chat completions carrying non-text content.

Two exchanges, one per non-text content kind the chat API takes: an image and
audio, both on the way in. Mistral has no audio output on this route.
Coverage records attribute names only, so what this scenario is really
checking is the *shape* of the recorded content: whether the message parts an
instrumentation writes into ``gen_ai.input.messages`` validate against the
registry schemas. Mistral reports audio input as seconds rather than tokens,
so that is the usage figure the audio exchange carries.
"""

import os

from mistralai.client import Mistral

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
AUDIO = "bW9jaw=="

client = Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL"))

client.chat.complete(
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

client.chat.complete(
    model="voxtral-mini-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What do you hear?"},
                {"type": "input_audio", "input_audio": AUDIO},
            ],
        },
    ],
    max_tokens=100,
    temperature=0.5,
)
