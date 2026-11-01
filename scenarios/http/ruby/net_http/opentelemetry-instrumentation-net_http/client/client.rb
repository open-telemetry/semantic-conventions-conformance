# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "opentelemetry/instrumentation/net/http"
require "opentelemetry/conformance/scenario_sdk"
require_relative "../../scenarios/client"

OpenTelemetry::Conformance::ScenarioSdk.run(
  instrumentation: "OpenTelemetry::Instrumentation::Net::HTTP"
) do
  NetHttpScenario.run
end
