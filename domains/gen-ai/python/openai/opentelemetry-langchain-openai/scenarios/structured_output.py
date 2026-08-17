# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an OpenAI JSON schema answer, through langchain.

``with_structured_output`` builds a chain, so this run also emits a workflow
span. That is langchain modelling structured output as a chain, not a scenario
straying out of the llm client group.
"""

from langchain_openai import ChatOpenAI

SCHEMA = {
    "title": "forecast",
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "temperature": {"type": "integer"},
        "conditions": {"enum": ["sunny", "cloudy", "rainy"]},
    },
    "required": ["location", "temperature", "conditions"],
}

model = ChatOpenAI(model="gpt-4o-mini", max_tokens=100, temperature=0.5)

model.with_structured_output(SCHEMA).invoke(
    [
        ("system", "You are a helpful assistant."),
        ("human", "What is the weather in Seattle?"),
    ]
)
