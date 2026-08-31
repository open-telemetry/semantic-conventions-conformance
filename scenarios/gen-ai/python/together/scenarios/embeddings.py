# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Together embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input; Together's
embeddings API takes neither an encoding format nor a dimension count, so this
request carries only the batch.
"""

from together import Together

Together().embeddings.create(
    model="BAAI/bge-large-en-v1.5",
    input=["Say this is a test", "And this is another one"],
)
