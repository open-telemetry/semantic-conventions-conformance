# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"
require "net/http"
require "socket"
require "timeout"
require_relative "../../../scenarios/server"

class RackServerScenarioTest < Minitest::Test
  def setup
    @request = Rack::MockRequest.new(RackServerScenario.application)
  end

  def test_serves_the_declared_routes
    assert_response(@request.get("/health"), 200, '{"ok": true}')
    assert_response(
      @request.get("/users/123?fields=name&verbose=true"),
      200,
      '{"id": 123, "name": "Alice"}'
    )
    assert_response(
      @request.get("/status/404"),
      404,
      '{"message": "status 404"}'
    )
    assert_response(
      @request.get("/status/500"),
      500,
      '{"message": "status 500"}'
    )
  end

  def test_reads_and_echoes_the_post_body
    response = @request.post(
      "/items",
      input: '{"name": "rack"}',
      "CONTENT_TYPE" => "application/json"
    )

    assert_response(
      response,
      201,
      '{"created": true, "payload": {"name": "rack"}}'
    )
  end

  def test_rejects_undeclared_routes_and_methods
    assert_response(
      @request.get("/missing"),
      404,
      '{"message": "no such route"}'
    )
    assert_response(
      @request.get("/items"),
      404,
      '{"message": "no such route"}'
    )
  end

  def test_stops_the_server_when_input_reaches_eof
    port = available_port
    input, driver = IO.pipe
    server = Thread.new do
      RackServerScenario.serve(
        RackServerScenario.application,
        input: input,
        port: port
      )
    end

    wait_until_ready(port)
    driver.close

    assert server.join(5), "server did not stop after stdin reached EOF"
  ensure
    driver&.close unless driver&.closed?
    input&.close unless input&.closed?
    server&.kill if server&.alive?
  end

  private

  def assert_response(response, status, body)
    assert_equal status, response.status
    assert_equal OpenTelemetry::Conformance::HTTP::CONTENT_TYPE,
                 response["content-type"]
    assert_equal body, response.body
  end

  def available_port
    socket = TCPServer.new("127.0.0.1", 0)
    socket.local_address.ip_port
  ensure
    socket&.close
  end

  def wait_until_ready(port)
    Timeout.timeout(5) do
      loop do
        response = Net::HTTP.new("127.0.0.1", port, nil).get("/health")
        return if response.code == "200"
      rescue Errno::ECONNREFUSED, Errno::ECONNRESET
        sleep 0.02
      end
    end
  end
end
