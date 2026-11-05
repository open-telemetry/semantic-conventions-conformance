# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an agno workflow, with no agent in it.

One function step passing a prompt to a model is the smallest workflow agno
runs without an agent, and that is what the conventions call a workflow. The
step calls the model itself rather than through an Agent step, so the workflow
span stands on its own.
"""

from agno.models.message import Message
from agno.models.openai import OpenAIChat
from agno.workflow import Step, StepInput, StepOutput, Workflow

model = OpenAIChat(id="gpt-4o-mini", temperature=0.5, max_tokens=100)


def answer(step_input: StepInput) -> StepOutput:
    response = model.response(
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content=step_input.input),
        ]
    )
    return StepOutput(content=response.content)


workflow = Workflow(
    name="conformance_workflow",
    steps=[Step(name="answer", executor=answer)],
)

workflow.run("Say this is a test")
