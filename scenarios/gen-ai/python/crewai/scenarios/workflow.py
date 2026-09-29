# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a CrewAI flow, with no agent around it.

Shared by every implementation under ``crewai/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

One step passing a prompt to a model is the smallest thing CrewAI calls a
flow, and a flow is what the conventions call a workflow. Kept free of crews,
agents and tools so the workflow span stands on its own.
"""

from crewai import LLM
from crewai.flow.flow import Flow, start


class AnswerFlow(Flow):
    @start()
    def answer(self) -> str:
        return LLM(
            model="openai/gpt-4o-mini", temperature=0.5, max_tokens=100
        ).call(
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say this is a test"},
            ]
        )


AnswerFlow().kickoff()
