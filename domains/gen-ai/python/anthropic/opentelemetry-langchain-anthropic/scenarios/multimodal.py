# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Anthropic non-text input, through langchain.

The same two exchanges as anthropic/scenarios/multimodal.py, an image and a
document, carried as content blocks on a human message.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
DOCUMENT = (
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+"
    "PgplbmRvYmoKdHJhaWxlcgo8PC9Sb290IDEgMCBSPj4K"
)

model = ChatAnthropic(
    model="claude-sonnet-4-20250514", max_tokens=100, temperature=0.5
)

model.invoke(
    [
        ("system", "You are a helpful assistant."),
        HumanMessage(
            content=[
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": IMAGE,
                    },
                },
            ]
        ),
    ]
)

model.invoke(
    [
        ("system", "You are a helpful assistant."),
        HumanMessage(
            content=[
                {"type": "text", "text": "Summarise this document."},
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": DOCUMENT,
                    },
                },
            ]
        ),
    ]
)
