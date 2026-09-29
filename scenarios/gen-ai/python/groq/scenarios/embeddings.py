# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Groq embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input and an
explicit encoding format, since each is an attribute the conventions declare
for this operation. Groq's embeddings API takes no dimension count.
"""

from groq import Groq

Groq().embeddings.create(
    model="nomic-embed-text-v1_5",
    input=["Say this is a test", "And this is another one"],
    encoding_format="float",
)
