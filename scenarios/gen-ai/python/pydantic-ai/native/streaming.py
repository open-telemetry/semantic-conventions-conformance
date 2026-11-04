# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

from scenarios import streaming  # noqa: E402

Agent.instrument_all(InstrumentationSettings(version=6))

streaming.run()
