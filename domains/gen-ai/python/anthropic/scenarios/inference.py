# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain anthropic message.

Shared by every implementation under ``anthropic/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The same exchange as every other library's inference scenario: a system
instruction and one user turn, carrying every sampling option the conventions
have an attribute for and Anthropic accepts. There is no seed and there are no
penalties in this API, so those are absent from the request rather than
silently missing from the coverage.
"""

from anthropic import Anthropic

Anthropic().messages.create(
    model="claude-sonnet-4-20250514",
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Say this is a test"}],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    top_k=10,
    stop_sequences=["\n\n"],
)
