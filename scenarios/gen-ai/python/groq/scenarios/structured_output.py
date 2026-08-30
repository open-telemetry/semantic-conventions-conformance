# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Groq chat completion with a JSON schema answer.

Asking for a schema is what ``gen_ai.output.type`` describes, so the request
names one rather than only asking for "some JSON".
"""

from groq import Groq

SCHEMA = {
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "temperature": {"type": "integer"},
        "conditions": {"enum": ["sunny", "cloudy", "rainy"]},
    },
    "required": ["location", "temperature", "conditions"],
    "additionalProperties": False,
}

# Groq allows `strict` json_schema only on GPT-OSS and Qwen 3.8 27B.
Groq().chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the weather in Seattle?"},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "forecast", "strict": True, "schema": SCHEMA},
    },
    max_tokens=100,
    temperature=0.5,
)
