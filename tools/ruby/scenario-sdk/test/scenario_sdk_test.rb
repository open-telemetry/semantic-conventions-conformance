# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"

$LOADED_FEATURES << "opentelemetry/sdk.rb"
$LOADED_FEATURES << "opentelemetry/exporter/otlp.rb"

module OpenTelemetry
  class << self
    attr_accessor :tracer_provider
  end

  module Exporter
    module OTLP
      class Exporter
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
    attr_reader :instrumentations, :processors

    def initialize
      @instrumentations = []
      @processors = []
    end

    def use(instrumentation)
      @instrumentations << instrumentation
    end

    def add_span_processor(processor)
      @processors << processor
    end
  end

  class Provider
    attr_reader :calls
    attr_accessor :fail_flush

    def initialize
      @calls = []
      @fail_flush = false
    end

    def force_flush
      @calls << :force_flush
      raise "flush failed" if fail_flush
    end

    def shutdown
      @calls << :shutdown
    end
  end

  def setup
    ENV["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://collector.test:4318"
    @configurator = Configurator.new
    @provider = Provider.new
    OpenTelemetry::ConformanceTest.configurator = @configurator
    OpenTelemetry.tracer_provider = @provider
  end

  def teardown
    ENV.delete("OTEL_EXPORTER_OTLP_ENDPOINT")
  end

  def test_configures_one_requested_instrumentation_and_the_otlp_exporter
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
  end

  def test_flushes_and_shuts_down_after_a_successful_workload
    OpenTelemetry::Conformance::ScenarioSdk.run(
      instrumentation: "Instrumentation"
    ) {}

    assert_equal([:force_flush, :shutdown], @provider.calls)
  end

  def test_flushes_and_shuts_down_after_a_failed_workload
    assert_raises(RuntimeError) do
      OpenTelemetry::Conformance::ScenarioSdk.run(
        instrumentation: "Instrumentation"
      ) { raise "workload failed" }
    end

    assert_equal([:force_flush, :shutdown], @provider.calls)
  end

  def test_shutdown_still_runs_when_flush_fails
    @provider.fail_flush = true

    assert_raises(RuntimeError) do
      OpenTelemetry::Conformance::ScenarioSdk.run(
        instrumentation: "Instrumentation"
      ) {}
    end

    assert_equal([:force_flush, :shutdown], @provider.calls)
  end
end
