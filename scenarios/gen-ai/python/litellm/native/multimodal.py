# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import multimodal

# Enable LiteLLM's built-in OpenTelemetry instrumentation
litellm.callbacks = ["otel"]

multimodal.run()
