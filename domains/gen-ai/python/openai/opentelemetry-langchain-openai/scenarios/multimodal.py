# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: OpenAI image input, through langchain.

langchain carries the image as a content block on a human message. Only the
image exchange is here: langchain has no audio output content block for chat
models, so that half of openai/scenarios/multimodal.py has no counterpart.
"""

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

model = ChatOpenAI(model="gpt-4o-mini", max_tokens=100, temperature=0.5)

model.invoke(
    [
        ("system", "You are a helpful assistant."),
        HumanMessage(
            content=[
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{IMAGE}"},
                },
            ]
        ),
    ]
)
