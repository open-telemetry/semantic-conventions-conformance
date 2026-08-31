# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import importlib
import sys
from pathlib import Path

# The shared programs, which sit beside the implementation directories rather
# than in any one of them. Found from this file rather than from `PYTHONPATH`,
# which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llama_index.observability.otel import LlamaIndexOpenTelemetry

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)

# The integration takes its configuration in code rather than from the
# environment, so it installs the provider here instead of running under
# `otel-conformance-python`. A simple processor exports each span as it ends,
# which is what leaves nothing to flush when the program exits.
LlamaIndexOpenTelemetry(
    span_exporter=OTLPSpanExporter(),
    span_processor="simple",
).start_registering()

importlib.import_module("scenarios.workflow")
