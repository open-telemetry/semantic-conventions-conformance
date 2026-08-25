# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from haystack_integrations.components.connectors.opentelemetry import (
    OpenTelemetryConnector,
)

from scenarios import workflow

# Haystack traces through a component in the pipeline.
workflow.pipeline.add_component("tracer", OpenTelemetryConnector())

workflow.run()
