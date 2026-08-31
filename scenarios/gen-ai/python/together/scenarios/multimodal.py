# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Together chat completions carrying non-text content.

Three exchanges, one per non-text content kind the chat API takes: an image, a
video and audio, all on the way in. Together has no non-text output on this
route. Audio has two spellings, a URL and inline data; the inline one is used
here because that is what the sibling scenarios send. Coverage records
attribute names only, so what this scenario is really checking is the *shape*
of the recorded content: whether the message parts an instrumentation writes
into ``gen_ai.input.messages`` validate against the registry schemas.
"""

from together import Together

# A 1x1 transparent PNG; nothing under test decodes it.
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
VIDEO = "https://example.com/mock.mp4"
AUDIO = "bW9jaw=="

client = Together()


def ask(model: str, question: str, part: dict) -> None:
    client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [{"type": "text", "text": question}, part],
            },
        ],
        max_tokens=100,
        temperature=0.5,
    )


ask(
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "What is in this image?",
    {"type": "image_url", "image_url": {"url": IMAGE}},
)

ask(
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "What happens in this video?",
    {"type": "video_url", "video_url": {"url": VIDEO}},
)

ask(
    "Qwen/Qwen2-Audio-7B-Instruct",
    "What do you hear?",
    {"type": "input_audio", "input_audio": {"data": AUDIO, "format": "wav"}},
)
