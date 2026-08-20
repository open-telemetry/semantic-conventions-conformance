# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: Bedrock Converse with tool use.

Two round trips, matching every other library's tool-calling scenario: the
tool definitions and the requested call, then the tool result travelling back
as input.
"""

import boto3

MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. Boston, MA",
                            }
                        },
                        "required": ["location"],
                    }
                },
            }
        }
    ]
}

client = boto3.client("bedrock-runtime")
messages = [
    {
        "role": "user",
        "content": [{"text": "What's the weather in Seattle today?"}],
    }
]

first = client.converse(
    modelId=MODEL,
    system=[{"text": "You are a helpful assistant."}],
    messages=messages,
    toolConfig=TOOL_CONFIG,
    inferenceConfig={"maxTokens": 100, "temperature": 0.5},
)

answer = first["output"]["message"]
messages.append(answer)
messages.append(
    {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": block["toolUse"]["toolUseId"],
                    "content": [
                        {
                            "text": "70 degrees and sunny in "
                            + block["toolUse"]["input"]["location"]
                        }
                    ],
                }
            }
            for block in answer["content"]
            if "toolUse" in block
        ],
    }
)

client.converse(
    modelId=MODEL,
    system=[{"text": "You are a helpful assistant."}],
    messages=messages,
    toolConfig=TOOL_CONFIG,
    inferenceConfig={"maxTokens": 100, "temperature": 0.5},
)
