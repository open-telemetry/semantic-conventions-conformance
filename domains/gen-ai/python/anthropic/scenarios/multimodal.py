# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: anthropic messages carrying non-text content.

Two exchanges, one per content kind Anthropic accepts alongside text: an image
and a document. Coverage records attribute names only, so what this checks is
the *shape* of the recorded content: whether the parts an instrumentation
writes into ``gen_ai.input.messages`` validate against the registry schemas.
"""

from anthropic import Anthropic

# A 1x1 transparent PNG and a one-page PDF; nothing under test decodes them.
IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
DOCUMENT = (
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+"
    "PgplbmRvYmoKdHJhaWxlcgo8PC9Sb290IDEgMCBSPj4K"
)

client = Anthropic()

client.messages.create(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": IMAGE,
                    },
                },
            ],
        }
    ],
    max_tokens=100,
    temperature=0.5,
)

client.messages.create(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarise this document."},
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": DOCUMENT,
                    },
                },
            ],
        }
    ],
    max_tokens=100,
    temperature=0.5,
)
