# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import litellm

# The shared programs, which sit beside the implementation directories rather
# than in any one of them. Found from this file rather than from `PYTHONPATH`,
# which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scenarios import embeddings  # noqa: E402

# Enable LiteLLM's built-in OpenTelemetry instrumentation
litellm.callbacks = ["otel"]

embeddings.run()
