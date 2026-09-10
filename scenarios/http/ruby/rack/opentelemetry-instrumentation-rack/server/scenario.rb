# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "opentelemetry/instrumentation/rack"
require "opentelemetry/conformance/scenario_sdk"
require_relative "../../scenarios/server"

OpenTelemetry::Conformance::ScenarioSdk.run(
  instrumentation: "OpenTelemetry::Instrumentation::Rack"
) do
  middleware =
    OpenTelemetry::Instrumentation::Rack::Instrumentation
      .instance
      .middleware_args
  application = Rack::Builder.new do
    use(*middleware)
    run RackServerScenario.application
  end

  RackServerScenario.serve(application)
end
