# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

$LOAD_PATH.unshift File.expand_path("../lib", __dir__)

require "minitest/autorun"
require "opentelemetry/conformance/http"

HTTP_CONTRACT = OpenTelemetry::Conformance::HTTP

module EnvironmentHelpers
  def with_environment(name, value)
    previous = ENV[name]
    if value.nil?
      ENV.delete(name)
    else
      ENV[name] = value
    end
    yield
  ensure
    if previous.nil?
      ENV.delete(name)
    else
      ENV[name] = previous
    end
  end
end

class Minitest::Test
  include EnvironmentHelpers
end
