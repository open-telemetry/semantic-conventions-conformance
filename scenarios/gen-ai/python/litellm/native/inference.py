# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import inference

# Enable LiteLLM's own OTel logger
litellm.callbacks = ["otel"]

inference.run()
