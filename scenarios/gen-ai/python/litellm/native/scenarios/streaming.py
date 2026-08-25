# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed litellm completion.

Same request as inference.py, delivered as a stream. The stream is consumed to
the end: an instrumentation cannot report the response or its token usage
before the last chunk arrives, so a scenario that abandoned the iterator would
measure the abandonment rather than the instrumentation.
"""

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor

litellm.callbacks = ["otel"]

stream = litellm.completion(
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
    stream=True,
    stream_options={"include_usage": True},
)

for _ in stream:
    pass

# LiteLLM runs its logging callbacks on a thread pool, so the span for the
# call above may not exist yet when this program returns. Waiting for that
# pool is what makes the run reproducible rather than a race with shutdown.
executor.shutdown(wait=True)
