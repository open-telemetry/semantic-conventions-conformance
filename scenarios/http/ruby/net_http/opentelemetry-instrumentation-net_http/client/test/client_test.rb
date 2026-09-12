# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"
require_relative "../../../scenarios/client"

class NetHttpScenarioClientTest < Minitest::Test
  HTTPContract = OpenTelemetry::Conformance::HTTP
  ACTIONS = '[{"request":{"method":"GET","path":"/health"},"response":{"status":200,"body":"{\"ok\": true}"}},{"request":{"method":"POST","path":"/items","body":"{\"name\": \"widget\"}"},"response":{"status":201,"body":"{\"created\": true, \"payload\": ${requestBody}}"}},{"request":{"method":"GET","path":"/status/500"},"response":{"status":500,"body":"{\"message\": \"status 500\"}"}}]'.freeze
  ACTION = '{"request":{"method":"POST","path":"/items","body":"{\"name\": \"widget\"}"},"response":{"status":201,"body":"{\"created\": true, \"payload\": ${requestBody}}"}}'.freeze

  Response = Struct.new(:code, :body)

  class FakeNetHTTP
    class << self
      attr_reader :instances

      def reset
        @instances = []
      end
    end

    attr_accessor :use_ssl
    attr_reader :host, :port, :requests, :starts

    def initialize(host, port)
      @host = host
      @port = port
      @requests = []
      @starts = 0
      self.class.instances << self
    end

    def start
      @starts += 1
      yield self
    end

    def request(request)
      @requests << request
      answer = HTTPContract.respond(request.method, request.path, request.body)
      Response.new(answer.status.to_s, answer.body)
    end
  end

  def setup
    FakeNetHTTP.reset
    ENV[HTTPContract::ACTIONS_VARIABLE] = ACTIONS
    ENV[HTTPContract::ACTION_VARIABLE] = ACTION
  end

  def test_runs_the_contract_over_one_connection
    capture_io do
      NetHttpScenario.run(
        "https://example.test:8443",
        http_class: FakeNetHTTP
      )
    end

    assert_equal 1, FakeNetHTTP.instances.length
    connection = FakeNetHTTP.instances.fetch(0)
    assert_equal "example.test", connection.host
    assert_equal 8443, connection.port
    assert_equal true, connection.use_ssl
    assert_equal 1, connection.starts
    assert_equal 1, connection.requests.length
    assert_equal ["/items"], connection.requests.map(&:path)
  end

  def test_sends_the_shared_headers_and_body
    capture_io do
      NetHttpScenario.run("http://example.test", http_class: FakeNetHTTP)
    end

    requests = FakeNetHTTP.instances.fetch(0).requests
    requests.each do |request|
      assert_equal HTTPContract::USER_AGENT, request["User-Agent"]
    end

    post = requests.find { |request| request.method == "POST" }
    assert_equal HTTPContract::CONTENT_TYPE, post["Content-Type"]
    assert_equal '{"name": "widget"}', post.body

    requests.reject { |request| request.equal?(post) }.each do |request|
      assert_nil request["Content-Type"]
      assert_nil request.body
    end
  end

  def test_returns_helper_responses_for_error_statuses
    client = NetHttpScenario::Client.new(
      "http://example.test",
      http_class: FakeNetHTTP
    )

    response = client.request(
      "GET",
      "http://example.test/status/500",
      nil
    )

    assert_instance_of HTTPContract::Response, response
    assert_equal 500, response.status
    assert_equal '{"message": "status 500"}', response.body
  end
end
