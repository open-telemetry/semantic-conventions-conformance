# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a streamed Bedrock Converse call.

Same request as inference.py, delivered as an event stream, consumed to the
end so the instrumentation sees the final event and its usage.
"""

import boto3

response = boto3.client("bedrock-runtime").converse_stream(
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

for _ in response["stream"]:
    pass
