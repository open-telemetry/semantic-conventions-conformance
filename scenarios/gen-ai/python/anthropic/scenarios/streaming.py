# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed anthropic message.

Same request as inference.py, delivered as a stream, consumed to the end so
the instrumentation sees the final message and its usage.
"""

from anthropic import Anthropic

with Anthropic().messages.stream(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Say this is a test"}],
    max_tokens=100,
    stop_sequences=["\n\n"],
    extra_body={"temperature": 0.5, "top_p": 0.9, "top_k": 10},
) as stream:
    for _ in stream:
        pass
