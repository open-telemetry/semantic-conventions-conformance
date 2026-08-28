# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a LlamaIndex workflow, with no agent around it.

Shared by every implementation under ``llama-index/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing.

One step passing a prompt to a model is the smallest thing LlamaIndex calls a
workflow, and that is what the conventions call a workflow too. Kept free of
tools and agents so the workflow span stands on its own.
"""

import asyncio

from llama_index.core.workflow import StartEvent, StopEvent, Workflow, step
from llama_index.llms.openai import OpenAI


class AnswerWorkflow(Workflow):
    @step
    async def answer(self, event: StartEvent) -> StopEvent:
        llm = OpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=100)
        response = await llm.acomplete(event.question)
        return StopEvent(result=str(response))


async def main() -> None:
    await AnswerWorkflow(timeout=60).run(question="Say this is a test")


asyncio.run(main())
