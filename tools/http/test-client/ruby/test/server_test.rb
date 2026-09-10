# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require_relative "test_helper"

class ServerTest < Minitest::Test
  def test_responds_from_the_contract
    response = HTTP_CONTRACT.respond("GET", "/status/500")

    assert_equal 500, response.status
    assert_equal '{"message": "status 500"}', response.body
    assert_predicate response, :frozen?
    assert_predicate response.body, :frozen?
  end

  def test_response_lookup_ignores_query
    assert_equal 200, HTTP_CONTRACT.respond("GET", "/users/123?fields=name").status
  end

  def test_echoes_the_body_that_arrived
    response = HTTP_CONTRACT.respond("POST", "/items", '{"name": "ruby"}')

    assert_equal 201, response.status
    assert_equal(
      '{"created": true, "payload": {"name": "ruby"}}',
      response.body
    )
  end

  def test_returns_not_found_for_unknown_traffic
    response = HTTP_CONTRACT.respond("GET", "/missing")

    assert_equal 404, response.status
    assert_equal '{"message": "no such route"}', response.body
  end

  def test_requires_the_mock_server_url
    [nil, "  "].each do |value|
      with_environment(HTTP_CONTRACT::MOCK_SERVER_URL_VARIABLE, value) do
        assert_raises(HTTP_CONTRACT::ConfigurationError) do
          HTTP_CONTRACT.mock_server_url
        end
      end
    end
  end

  def test_reads_the_mock_server_url
    with_environment(
      HTTP_CONTRACT::MOCK_SERVER_URL_VARIABLE,
      "http://127.0.0.1:4321"
    ) do
      assert_equal "http://127.0.0.1:4321", HTTP_CONTRACT.mock_server_url
    end
  end

  def test_requires_the_scenario_port
    [nil, "  "].each do |value|
      with_environment(HTTP_CONTRACT::PORT_VARIABLE, value) do
        error = assert_raises(HTTP_CONTRACT::ConfigurationError) do
          HTTP_CONTRACT.scenario_port
        end
        assert_includes error.message, "otel-http-drive"
      end
    end
  end

  def test_rejects_an_invalid_scenario_port
    ["not-a-port", "0", "65536"].each do |value|
      with_environment(HTTP_CONTRACT::PORT_VARIABLE, value) do
        error = assert_raises(HTTP_CONTRACT::ConfigurationError) do
          HTTP_CONTRACT.scenario_port
        end
        assert_includes error.message, value
      end
    end
  end

  def test_reads_the_scenario_port
    with_environment(HTTP_CONTRACT::PORT_VARIABLE, "4321") do
      assert_equal 4321, HTTP_CONTRACT.scenario_port
    end
  end
end
