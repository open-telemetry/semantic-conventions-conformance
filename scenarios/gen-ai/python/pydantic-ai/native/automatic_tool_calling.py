# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

from scenarios import automatic_tool_calling

# Pydantic AI's own instrumentation, on its latest telemetry format.
Agent.instrument_all(InstrumentationSettings(version=6))

automatic_tool_calling.run()
