# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import structured_output

# Enable LiteLLM's built-in OpenTelemetry instrumentation
litellm.callbacks = ["otel"]

structured_output.run()
