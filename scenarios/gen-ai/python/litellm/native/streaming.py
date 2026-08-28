# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import streaming

# Enable LiteLLM's own OTel logger
litellm.callbacks = ["otel"]

streaming.run()
