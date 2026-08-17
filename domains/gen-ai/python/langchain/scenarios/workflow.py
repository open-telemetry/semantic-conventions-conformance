# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a langchain chain, with no agent around it.

Shared by every implementation under ``langchain/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

A prompt piped into a model is the smallest thing langchain calls a chain, and
a chain is what the conventions call a workflow. Kept free of tools and agents
so the workflow span stands on its own.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant."),
        ("human", "{question}"),
    ]
)
chain = (
    prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=100)
).with_config(run_name="conformance_workflow")

chain.invoke({"question": "Say this is a test"})
