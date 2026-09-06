# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Mistral chat completion.

Same request as inference.py, delivered as a stream. The stream is consumed to
the end: an instrumentation cannot report the response or its token usage
before the last chunk arrives, so a scenario that abandoned the iterator would
measure the abandonment rather than the instrumentation.
"""

import os

from mistralai.client import Mistral

stream = Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL")).chat.stream(
    model="mistral-small-latest",
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
    random_seed=42,
)

for _ in stream:
    pass
