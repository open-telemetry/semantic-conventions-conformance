# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require_relative "test_helper"

class ClientTest < Minitest::Test
  BASE_URL = "http://127.0.0.1:1".freeze

  def test_drives_measured_requests_through_the_supplied_sender
    sent = []
    sender = lambda do |method, url, body|
      target = url.delete_prefix(BASE_URL)
      sent << "#{method} #{target}"
      HTTP_CONTRACT.respond(method, target, body)
    end

    capture_io { HTTP_CONTRACT.drive("#{BASE_URL}/", sender) }

    assert_equal(
      [
        "GET /users/123",
        "GET /users/123?fields=name&verbose=true",
        "POST /items",
        "GET /status/404",
        "GET /status/500"
      ],
      sent
    )
  end

  def test_compares_json_by_structure
    exchange = HTTP_CONTRACT.exchange_for("GET", "/users/123")
    response = HTTP_CONTRACT::Response.new(
      status: exchange.status,
      body: %({"name":"Alice",\n"id":123})
    )

    assert_nil HTTP_CONTRACT.verify(exchange, response)
  end

  def test_rejects_a_bad_status
    exchange = HTTP_CONTRACT.exchange_for("GET", "/users/123")
    response = HTTP_CONTRACT::Response.new(
      status: 500,
      body: exchange.response_body
    )

    error = assert_raises(HTTP_CONTRACT::ContractError) do
      HTTP_CONTRACT.verify(exchange, response)
    end
    assert_includes error.message, "answered 500"
  end

  def test_rejects_a_bad_json_body
    exchange = HTTP_CONTRACT.exchange_for("GET", "/users/123")
    response = HTTP_CONTRACT::Response.new(status: exchange.status, body: "<html>")

    error = assert_raises(HTTP_CONTRACT::ContractError) do
      HTTP_CONTRACT.verify(exchange, response)
    end
    assert_match(/\Anot JSON:/, error.message)
  end

  def test_rejects_the_wrong_json_structure
    exchange = HTTP_CONTRACT.exchange_for("GET", "/users/123")
    response = HTTP_CONTRACT::Response.new(
      status: exchange.status,
      body: '{"id":124,"name":"Alice"}'
    )

    assert_raises(HTTP_CONTRACT::ContractError) do
      HTTP_CONTRACT.verify(exchange, response)
    end
  end

  def test_rejects_a_blank_base_url_before_sending
    sent = false

    assert_raises(ArgumentError) do
      HTTP_CONTRACT.drive("  ", ->(*_arguments) { sent = true })
    end
    refute sent
  end
end
