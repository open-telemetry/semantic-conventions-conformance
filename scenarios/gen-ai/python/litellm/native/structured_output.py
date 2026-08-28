# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import litellm

from scenarios import structured_output

# Enable LiteLLM's own OTel logger
litellm.callbacks = ["otel"]

structured_output.run()
