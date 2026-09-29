# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Mistral chat completion with a JSON schema answer.

Asking for a schema is what ``gen_ai.output.type`` describes, so the request
names one rather than only asking for "some JSON".
"""

import os

from mistralai.client import Mistral

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

Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL")).chat.complete(
    model="mistral-small-latest",
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
