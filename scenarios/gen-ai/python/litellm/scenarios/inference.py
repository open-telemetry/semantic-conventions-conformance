# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain litellm completion.

Shared by every implementation under ``litellm/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The request carries every sampling option the conventions have an attribute
for and the OpenAI route accepts, because an attribute missing from the
coverage of a request that never set it says nothing about the
instrumentation. OpenAI has no top-k.
"""

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor


def run() -> None:
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
        service_tier="default",
    )
    # shut down the thread pool executor to ensure all instrumentation callbacks are completed
    executor.shutdown(wait=True)


if __name__ == "__main__":
    run()
