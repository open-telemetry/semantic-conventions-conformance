# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single dspy agent run.

dspy's agent is ``dspy.ReAct``, and it accepts an empty tool list: the run is
then the agent and its built-in ``finish`` step, with no tool of the caller's.
That is what makes the agent span readable on its own.
"""

import dspy

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", temperature=0.5, max_tokens=100, cache=False))

agent = dspy.ReAct("question -> answer", tools=[])
agent(question="Say this is a test")
