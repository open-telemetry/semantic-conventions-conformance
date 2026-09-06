# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Together chat completion.

Same request as inference.py, delivered as a stream. The stream is consumed to
the end: an instrumentation cannot report the response or its token usage
before the last chunk arrives, so a scenario that abandoned the iterator would
measure the abandonment rather than the instrumentation.
"""

from together import Together

stream = Together().chat.completions.create(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    top_k=40,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    seed=42,
    stream=True,
)

for _ in stream:
    pass
