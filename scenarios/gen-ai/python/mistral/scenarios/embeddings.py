# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Mistral embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input, an
explicit dimension count and an explicit encoding format, since each is an
attribute the conventions declare for this operation.
"""

import os

from mistralai.client import Mistral

Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL")).embeddings.create(
    model="mistral-embed",
    inputs=["Say this is a test", "And this is another one"],
    output_dimension=256,
    encoding_format="float",
)
