# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"

$LOADED_FEATURES << "opentelemetry/sdk.rb"
$LOADED_FEATURES << "opentelemetry/exporter/otlp.rb"
$LOADED_FEATURES << "opentelemetry-metrics-sdk.rb"
$LOADED_FEATURES << "opentelemetry-exporter-otlp-metrics.rb"

module OpenTelemetry
  class << self
    attr_accessor :tracer_provider
    attr_accessor :meter_provider
  end

  module Exporter
    module OTLP
      class Exporter
      end

      module Metrics
        class MetricsExporter
        end
      end
    end
  end

  module SDK
    module Trace
      module Export
        class BatchSpanProcessor
          attr_reader :exporter

          def initialize(exporter)
            @exporter = exporter
          end
        end
      end
    end

    module Metrics
      module Export
        class PeriodicMetricReader
          attr_reader :exporter

          def initialize(exporter:)
            @exporter = exporter
          end
        end
      end
    end

    def self.configure
      yield OpenTelemetry::ConformanceTest.configurator
    end
  end

  module ConformanceTest
    class << self
      attr_accessor :configurator
    end
  end
end

require "opentelemetry/conformance/scenario_sdk"

class ScenarioSdkTest < Minitest::Test
  class Configurator
    attr_reader :instrumentations, :processors, :readers

    def initialize
      @instrumentations = []
      @processors = []
      @readers = []
    end

    def use(instrumentation)
      @instrumentations << instrumentation
    end

    def add_span_processor(processor)
      @processors << processor
    end

    def add_metric_reader(reader)
      @readers << reader
    end
  end

  class Provider
    attr_accessor :fail_flush

    def initialize(name, calls)
      @name = name
      @calls = calls
      @fail_flush = false
    end

    def force_flush
      @calls << [@name, :force_flush]
      raise "flush failed" if fail_flush
    end

    def shutdown
      @calls << [@name, :shutdown]
    end
  end

  def setup
    ENV["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://collector.test:4318"
    @configurator = Configurator.new
    @lifecycle_calls = []
    @tracer_provider = Provider.new(:trace, @lifecycle_calls)
    @meter_provider = Provider.new(:metrics, @lifecycle_calls)
    OpenTelemetry::ConformanceTest.configurator = @configurator
    OpenTelemetry.tracer_provider = @tracer_provider
    OpenTelemetry.meter_provider = @meter_provider
  end

  def teardown
    ENV.delete("OTEL_EXPORTER_OTLP_ENDPOINT")
  end

  def test_configures_one_requested_instrumentation_and_the_otlp_exporters
    OpenTelemetry::Conformance::ScenarioSdk.run(
      instrumentation: "OpenTelemetry::Instrumentation::Net::HTTP"
    ) {}

    assert_equal(
      ["OpenTelemetry::Instrumentation::Net::HTTP"],
      @configurator.instrumentations
    )
    assert_equal(1, @configurator.processors.length)
    assert_instance_of(
      OpenTelemetry::Exporter::OTLP::Exporter,
      @configurator.processors.first.exporter
    )
    assert_equal(1, @configurator.readers.length)
    assert_instance_of(
      OpenTelemetry::Exporter::OTLP::Metrics::MetricsExporter,
      @configurator.readers.first.exporter
    )
  end

  def test_flushes_both_providers_before_shutting_them_down
    OpenTelemetry::Conformance::ScenarioSdk.run(
      instrumentation: "Instrumentation"
    ) {}

    assert_lifecycle
  end

  def test_flushes_and_shuts_down_both_providers_after_a_failed_workload
    assert_raises(RuntimeError) do
      OpenTelemetry::Conformance::ScenarioSdk.run(
        instrumentation: "Instrumentation"
      ) { raise "workload failed" }
    end

    assert_lifecycle
  end

  def test_other_provider_flushes_and_both_shutdowns_when_trace_flush_fails
    @tracer_provider.fail_flush = true

    assert_raises(RuntimeError) do
      OpenTelemetry::Conformance::ScenarioSdk.run(
        instrumentation: "Instrumentation"
      ) {}
    end

    assert_lifecycle
  end

  def test_both_providers_shut_down_when_metric_flush_fails
    @meter_provider.fail_flush = true

    assert_raises(RuntimeError) do
      OpenTelemetry::Conformance::ScenarioSdk.run(
        instrumentation: "Instrumentation"
      ) {}
    end

    assert_lifecycle
  end

  private

  def assert_lifecycle
    assert_equal(
      [
        [:trace, :force_flush],
        [:metrics, :force_flush],
        [:trace, :shutdown],
        [:metrics, :shutdown]
      ],
      @lifecycle_calls
    )
  end
end
