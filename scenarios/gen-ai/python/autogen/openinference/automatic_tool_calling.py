# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import importlib

from autogen_agentchat.agents import _base_chat_agent
from autogen_core.tools import _base as _tool_base


def _no_span(*_args, **_kwargs):
    return contextlib.nullcontext()


# AutoGen traces its agent and tool operations itself, with no switch to turn
# that off, and those spans would land in this report beside OpenInference's.
# Patching the helpers where AutoGen imports them is what the reference
# scenarios in semantic-conventions-genai do.
_base_chat_agent.trace_create_agent_span = _no_span
_base_chat_agent.trace_invoke_agent_span = _no_span
_tool_base.trace_tool_span = _no_span

importlib.import_module("scenarios.automatic_tool_calling")
