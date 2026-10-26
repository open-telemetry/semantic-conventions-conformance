# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require_relative "test_helper"

class ContractTest < Minitest::Test
  def test_reads_every_contract_field
    refute_empty HTTP_CONTRACT.exchanges

    HTTP_CONTRACT.exchanges.each do |exchange|
      refute_empty exchange.description
      refute_empty exchange.method
      refute_empty exchange.path
      assert_kind_of Integer, exchange.status
      assert_kind_of String, exchange.response_body
      assert_includes [true, false], exchange.readiness
      assert(exchange.body.nil? || exchange.body.is_a?(String))
    end
  end

  def test_exchange_data_is_immutable
    assert_predicate HTTP_CONTRACT.exchanges, :frozen?
    assert_predicate HTTP_CONTRACT.requests, :frozen?
    assert_predicate HTTP_CONTRACT.exchanges.first, :frozen?
    assert_predicate HTTP_CONTRACT.exchanges.first.path, :frozen?
  end

  def test_excludes_readiness_from_measured_requests
    assert HTTP_CONTRACT.exchanges.any?(&:readiness)
    refute HTTP_CONTRACT.requests.any?(&:readiness)
    assert_equal HTTP_CONTRACT.exchanges.length - 1, HTTP_CONTRACT.requests.length
  end

  def test_lookup_ignores_query_but_checks_method
    plain = HTTP_CONTRACT.exchange_for("GET", "/users/123")
    queried = HTTP_CONTRACT.exchange_for("GET", "/users/123?fields=name")

    assert_equal plain.status, queried.status
    assert_equal plain.response_body, queried.response_body
    assert_nil HTTP_CONTRACT.exchange_for("DELETE", "/users/123")
    assert_nil HTTP_CONTRACT.exchange_for("GET", "/missing")
  end

  def test_renders_the_request_body
    exchange = HTTP_CONTRACT.exchange_for("POST", "/items")

    assert_equal(
      '{"created": true, "payload": {"name": "widget"}}',
      exchange.render_response_body('{"name": "widget"}')
    )
    assert_equal(
      '{"created": true, "payload": {}}',
      exchange.render_response_body(nil)
    )
  end

  def test_defines_fixed_headers
    assert_equal(
      { "User-Agent" => "otel-http-conformance/1" },
      HTTP_CONTRACT.client_headers(nil)
    )
    assert_equal(
      {
        "User-Agent" => "otel-http-conformance/1",
        "Content-Type" => "application/json"
      },
      HTTP_CONTRACT.client_headers('{"name":"widget"}')
    )
  end
end
