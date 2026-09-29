# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

# The shared programs, which sit beside the implementation directories rather
# than in any one of them. Found from this file rather than from `PYTHONPATH`,
# which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from haystack_integrations.components.connectors.opentelemetry import (
    OpenTelemetryConnector,
)

from scenarios import workflow  # noqa: E402

# Haystack traces through a component in the pipeline.
workflow.pipeline.add_component("tracer", OpenTelemetryConnector())

workflow.run()
