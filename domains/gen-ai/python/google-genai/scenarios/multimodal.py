# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: google-genai calls carrying non-text content.

Two exchanges: an image on the way in, and an image asked for on the way out.
Coverage records attribute names only, so what this checks is the *shape* of
the recorded content: whether the parts an instrumentation writes into
``gen_ai.input.messages`` and ``gen_ai.output.messages`` validate against the
registry schemas. It also covers the per-modality token counts Gemini reports.
"""

import base64

from google import genai
from google.genai import types

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

client = genai.Client()

client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        types.Content(
            role="user",
            parts=[
                types.Part(text="What is in this image?"),
                types.Part.from_bytes(data=IMAGE, mime_type="image/png"),
            ],
        )
    ],
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        max_output_tokens=100,
        temperature=0.5,
    ),
)

client.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents="Draw a picture of a cat",
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",
        response_modalities=["TEXT", "IMAGE"],
        max_output_tokens=100,
        temperature=0.5,
    ),
)
