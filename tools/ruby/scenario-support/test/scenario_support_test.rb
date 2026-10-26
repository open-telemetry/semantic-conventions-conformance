# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"
require "stringio"
require "opentelemetry/conformance/scenario_support"

class ScenarioSupportTest < Minitest::Test
  def test_required_environment_value
    ENV["CONFORMANCE_TEST_VALUE"] = "present"

    assert_equal(
      "present",
      OpenTelemetry::Conformance::ScenarioEnvironment.require(
        "CONFORMANCE_TEST_VALUE"
      )
    )
  ensure
    ENV.delete("CONFORMANCE_TEST_VALUE")
  end

  def test_missing_environment_value
    error = assert_raises(KeyError) do
      OpenTelemetry::Conformance::ScenarioEnvironment.require(
        "CONFORMANCE_MISSING_VALUE"
      )
    end

    assert_includes(error.message, "CONFORMANCE_MISSING_VALUE")
  end

  def test_wait_for_eof_consumes_the_input
    input = StringIO.new("ignored")

    OpenTelemetry::Conformance::ScenarioLifecycle.wait_for_eof(input)

    assert_predicate(input, :eof?)
  end
end
