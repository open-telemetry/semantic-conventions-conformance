# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Cohere embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input, an
explicit dimension count and an explicit encoding format, since each is an
attribute the conventions declare for this operation. Cohere calls the
encoding format an embedding type, and needs to be told what the input is for.
"""

import cohere

cohere.ClientV2().embed(
    model="embed-v4.0",
    texts=["Say this is a test", "And this is another one"],
    input_type="search_document",
    embedding_types=["float"],
    output_dimension=256,
)
