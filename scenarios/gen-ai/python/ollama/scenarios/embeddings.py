# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Ollama embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input and an
explicit dimension count, since each is an attribute the conventions declare
for this operation. Ollama's embed API takes no encoding format.
"""

from ollama import embed

embed(
    model="nomic-embed-text",
    input=["Say this is a test", "And this is another one"],
    dimensions=256,
)
