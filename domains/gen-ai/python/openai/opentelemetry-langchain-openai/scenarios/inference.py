# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain OpenAI chat completion, through langchain.

The same exchange as openai/scenarios/inference.py, made through ChatOpenAI
instead of the openai client, so the two data.json files compare directly.
Nothing here turns instrumentation on, and nothing here may.
"""

from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-4o-mini",
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    seed=42,
)

model.invoke(
    [
        ("system", "You are a helpful assistant."),
        ("human", "Say this is a test"),
    ]
)
