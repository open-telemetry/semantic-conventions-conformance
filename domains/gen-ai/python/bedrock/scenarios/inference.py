# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Bedrock Converse call.

Shared by every implementation under ``bedrock/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The same exchange as every other library's inference scenario: a system
instruction and one user turn, carrying every sampling option the conventions
have an attribute for and Converse accepts. Bedrock has no seed and no
penalties, so those are absent from the request.
"""

import boto3

boto3.client("bedrock-runtime").converse(
    modelId="anthropic.claude-3-5-sonnet-20240620-v1:0",
    system=[{"text": "You are a helpful assistant."}],
    messages=[{"role": "user", "content": [{"text": "Say this is a test"}]}],
    inferenceConfig={
        "maxTokens": 100,
        "temperature": 0.5,
        "topP": 0.9,
        "stopSequences": ["\n\n"],
    },
)
