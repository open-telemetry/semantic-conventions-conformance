# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

$LOAD_PATH.unshift File.expand_path("../lib", __dir__)

require "minitest/autorun"
require "json"
require "opentelemetry/conformance/http"

HTTP_CONTRACT = OpenTelemetry::Conformance::HTTP
HTTP_ACTIONS = [
  {
    "request" => {"method" => "GET", "path" => "/health"},
    "response" => {"status" => 200, "body" => '{"ok": true}'}
  },
  {
    "request" => {"method" => "GET", "path" => "/users/123"},
    "response" => {
      "status" => 200,
      "body" => '{"id": 123, "name": "Alice"}'
    }
  },
  {
    "request" => {
      "method" => "GET",
      "path" => "/users/123?fields=name&verbose=true"
    },
    "response" => {
      "status" => 200,
      "body" => '{"id": 123, "name": "Alice"}'
    }
  },
  {
    "request" => {
      "method" => "POST",
      "path" => "/items",
      "body" => '{"name": "widget"}'
    },
    "response" => {
      "status" => 201,
      "body" => '{"created": true, "payload": ${requestBody}}'
    }
  },
  {
    "request" => {"method" => "GET", "path" => "/status/404"},
    "response" => {"status" => 404, "body" => '{"message": "status 404"}'}
  },
  {
    "request" => {"method" => "GET", "path" => "/status/500"},
    "response" => {"status" => 500, "body" => '{"message": "status 500"}'}
  }
].freeze
ENV[HTTP_CONTRACT::ACTIONS_VARIABLE] = JSON.generate(HTTP_ACTIONS)
ENV[HTTP_CONTRACT::ACTION_VARIABLE] = JSON.generate(HTTP_ACTIONS.fetch(1))

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
