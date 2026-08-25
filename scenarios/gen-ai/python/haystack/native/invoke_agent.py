# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from haystack_integrations.components.connectors.opentelemetry import (
    OpenTelemetryConnector,
)

from scenarios import invoke_agent

# Haystack traces through a component in the pipeline.
invoke_agent.pipeline.add_component("tracer", OpenTelemetryConnector())

invoke_agent.run()
