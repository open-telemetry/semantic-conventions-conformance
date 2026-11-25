# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
from pathlib import Path

# The shared programs, which sit beside the implementation directories rather
# than in any one of them. Found from this file rather than from `PYTHONPATH`,
# which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opentelemetry.sdk._logs import LoggingHandler  # noqa: E402
from scenarios import automatic_tool_calling  # noqa: E402

# Semantic Kernel writes prompt and completion content as stdlib logging
# records from its model diagnostics, not as span attributes. Bridge that
# logger, and only it, to the logger provider the launcher installed.
diagnostics = logging.getLogger(
    "semantic_kernel.utils.telemetry.model_diagnostics"
)
diagnostics.setLevel(logging.INFO)
diagnostics.addHandler(LoggingHandler())

automatic_tool_calling.run()
