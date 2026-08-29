# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Ollama embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input; Ollama's
embed API takes neither an encoding format nor a dimension count, so this
request carries only the batch.
"""

from ollama import embed

embed(
    model="nomic-embed-text",
    input=["Say this is a test", "And this is another one"],
)
