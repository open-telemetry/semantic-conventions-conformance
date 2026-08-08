# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: openai chat completion (inference).

Shared by every implementation under ``openai/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.
"""

from openai import OpenAI

OpenAI().chat.completions.create(
    messages=[{"role": "user", "content": "Say this is a test"}],
    model="gpt-4o-mini",
    stream=False,
)
