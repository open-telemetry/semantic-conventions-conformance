# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import embeddings

# Enable LiteLLM's built-in OpenTelemetry instrumentation
litellm.callbacks = ["otel"]

embeddings.run()
