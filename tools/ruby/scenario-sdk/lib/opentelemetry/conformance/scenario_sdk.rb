# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry-metrics-sdk"
require "opentelemetry-exporter-otlp-metrics"
require "opentelemetry/conformance/scenario_support"

module OpenTelemetry
  module Conformance
    # The telemetry SDK owned by an explicitly instrumented Ruby scenario.
    module ScenarioSdk
      module_function

      # Runs a workload with exactly one instrumentation and OTLP exporters.
      def run(instrumentation:)
        unless instrumentation.is_a?(String) && !instrumentation.strip.empty?
          raise ArgumentError, "instrumentation must be a nonblank name"
        end

        ScenarioEnvironment.require("OTEL_EXPORTER_OTLP_ENDPOINT")
        span_processor =
          OpenTelemetry::SDK::Trace::Export::BatchSpanProcessor.new(
            OpenTelemetry::Exporter::OTLP::Exporter.new
          )
        metric_reader =
          OpenTelemetry::SDK::Metrics::Export::PeriodicMetricReader.new(
            exporter:
              OpenTelemetry::Exporter::OTLP::Metrics::MetricsExporter.new
          )

        OpenTelemetry::SDK.configure do |config|
          config.add_span_processor(span_processor)
          config.add_metric_reader(metric_reader)
          config.use(instrumentation)
        end
        tracer_provider = OpenTelemetry.tracer_provider
        meter_provider = OpenTelemetry.meter_provider

        begin
          yield
        ensure
          begin
            tracer_provider.force_flush
          ensure
            begin
              meter_provider.force_flush
            ensure
              begin
                tracer_provider.shutdown
              ensure
                meter_provider.shutdown
              end
            end
          end
        end
      end
    end
  end
end
