# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import embeddings

# Enable LiteLLM's own OTel logger
litellm.callbacks = ["otel"]

embeddings.run()
