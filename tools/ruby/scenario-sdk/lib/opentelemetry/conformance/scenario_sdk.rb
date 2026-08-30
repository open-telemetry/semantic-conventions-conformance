# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/conformance/scenario_support"

module OpenTelemetry
  module Conformance
    # The tracing SDK owned by an explicitly instrumented Ruby scenario.
    module ScenarioSdk
      module_function

      # Runs a workload with exactly one instrumentation and the OTLP exporter.
      def run(instrumentation:)
        unless instrumentation.is_a?(String) && !instrumentation.strip.empty?
          raise ArgumentError, "instrumentation must be a nonblank name"
        end

        ScenarioEnvironment.require("OTEL_EXPORTER_OTLP_ENDPOINT")
        exporter = OpenTelemetry::Exporter::OTLP::Exporter.new
        processor =
          OpenTelemetry::SDK::Trace::Export::BatchSpanProcessor.new(exporter)

        OpenTelemetry::SDK.configure do |config|
          config.add_span_processor(processor)
          config.use(instrumentation)
        end
        provider = OpenTelemetry.tracer_provider

        begin
          yield
        ensure
          begin
            provider.force_flush
          ensure
            provider.shutdown
          end
        end
      end
    end
  end
end
