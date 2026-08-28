# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: litellm completions carrying non-text content.

Two exchanges, one per modality that changes what the telemetry has to say:
an image on the way in, and audio on both sides. Coverage records attribute
names only, so what this scenario is really checking is the *shape* of the
recorded content: whether the message parts an instrumentation writes into
``gen_ai.input.messages`` and ``gen_ai.output.messages`` validate against the
registry schemas. It also covers the per-modality token counts the provider
reports back.
"""

import litellm
from litellm.litellm_core_utils.thread_pool_executor import executor

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
AUDIO = "bW9jaw=="


def run() -> None:
    litellm.completion(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": IMAGE}},
                ],
            },
        ],
        max_tokens=100,
        temperature=0.5,
    )

    litellm.completion(
        model="openai/gpt-4o-audio-preview",
        modalities=["text", "audio"],
        audio={"voice": "alloy", "format": "wav"},
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Repeat what you hear."},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": AUDIO, "format": "wav"},
                    },
                ],
            },
        ],
        max_tokens=100,
        temperature=0.5,
    )
    # shut down the thread pool executor to ensure all instrumentation callbacks are completed
    executor.shutdown(wait=True)


if __name__ == "__main__":
    run()
