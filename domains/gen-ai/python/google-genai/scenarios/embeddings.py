# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: google-genai embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input and an
explicit dimension count, since each is an attribute the conventions declare
for this operation.
"""

from google import genai
from google.genai import types

client = genai.Client()

client.models.embed_content(
    model="text-embedding-004",
    contents=["Say this is a test", "And this is another one"],
    config=types.EmbedContentConfig(output_dimensionality=256),
)
