# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain litellm completion.

LiteLLM's OpenTelemetry logger is part of the library, so turning it on is a
line of litellm's own API rather than an instrumentation package. That is the
only thing this program says about telemetry.

The request carries every sampling option the conventions have an attribute
for and the OpenAI route accepts, because an attribute missing from the
coverage of a request that never set it says nothing about the
instrumentation. OpenAI has no top-k.
"""

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor

litellm.callbacks = ["otel"]

litellm.completion(
    model="openai/gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    seed=42,
)

# LiteLLM runs its logging callbacks on a thread pool, so the span for the
# call above may not exist yet when this program returns. Waiting for that
# pool is what makes the run reproducible rather than a race with shutdown.
executor.shutdown(wait=True)
