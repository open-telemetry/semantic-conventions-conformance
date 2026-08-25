# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from haystack_integrations.components.connectors.opentelemetry import (
    OpenTelemetryConnector,
)

from scenarios import automatic_tool_calling

# Haystack traces through a component in the pipeline.
automatic_tool_calling.pipeline.add_component("tracer", OpenTelemetryConnector())

automatic_tool_calling.run()
