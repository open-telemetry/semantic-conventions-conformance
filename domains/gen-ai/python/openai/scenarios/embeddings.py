# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: openai embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input, an
explicit encoding format and an explicit dimension count, since each is an
attribute the conventions declare for this operation.
"""

from openai import OpenAI

OpenAI().embeddings.create(
    model="text-embedding-3-small",
    input=["Say this is a test", "And this is another one"],
    encoding_format="float",
    dimensions=256,
)
