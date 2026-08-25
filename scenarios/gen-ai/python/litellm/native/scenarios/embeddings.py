# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: litellm embeddings.

A different operation, so a different span type, which is why this is its own
program rather than another call inside inference.py. Batched input, an
explicit encoding format and an explicit dimension count, since each is an
attribute the conventions declare for this operation.
"""

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor

litellm.callbacks = ["otel"]

litellm.embedding(
    model="openai/text-embedding-3-small",
    input=["Say this is a test", "And this is another one"],
    encoding_format="float",
    dimensions=256,
)

# LiteLLM runs its logging callbacks on a thread pool, so the span for the
# call above may not exist yet when this program returns. Waiting for that
# pool is what makes the run reproducible rather than a race with shutdown.
executor.shutdown(wait=True)
