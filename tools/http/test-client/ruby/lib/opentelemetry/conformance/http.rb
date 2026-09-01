# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "json"
require_relative "http/version"

module OpenTelemetry
  module Conformance
    # Reads and exercises the shared HTTP conformance contract.
    module HTTP
      CONTENT_TYPE = "application/json".freeze
      USER_AGENT = "otel-http-conformance/1".freeze
      PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT".freeze
      MOCK_SERVER_URL_VARIABLE = "MOCK_SERVER_URL".freeze
      CONTRACT = File.expand_path("../../../../contract.json", __dir__).freeze

      class ContractError < StandardError; end
      class ConfigurationError < StandardError; end

      # One concrete request and its required answer.
      class Exchange
        attr_reader :method, :path, :body, :status, :response_body,
                    :readiness, :description

        def initialize(method:, path:, body:, status:, response_body:,
                       readiness:, description:)
          @method = immutable_string(method)
          @path = immutable_string(path)
          @body = body.nil? ? nil : immutable_string(body)
          @status = status
          @response_body = immutable_string(response_body)
          @readiness = readiness
          @description = immutable_string(description)
          freeze
        end

        def render_response_body(request_body)
          replacement = request_body.nil? || request_body.empty? ? "{}" : request_body
          response_body.sub("${requestBody}") { replacement }
        end

        private

        def immutable_string(value)
          String(value).dup.freeze
        end
      end

      # A status and body returned by a sender or route.
      class Response
        attr_reader :status, :body

        def initialize(status:, body:)
          @status = status
          @body = String(body).dup.freeze
          freeze
        end
      end

      document = JSON.parse(File.read(CONTRACT, encoding: "UTF-8"))
      EXCHANGES = document.fetch("requests").map do |entry|
        Exchange.new(
          method: entry.fetch("method"),
          path: entry.fetch("path"),
          body: entry["body"],
          status: entry.fetch("status"),
          response_body: entry.fetch("responseBody"),
          readiness: entry.fetch("readiness", false),
          description: entry.fetch("description")
        )
      end.freeze
      REQUESTS = EXCHANGES.reject(&:readiness).freeze

      module_function

      # Every exchange, including readiness, in contract order.
      def exchanges
        EXCHANGES
      end

      # The measured exchanges, in contract order.
      def requests
        REQUESTS
      end

      # Finds an exchange by exact method and path, ignoring its query.
      def exchange_for(method, target)
        path = without_query(target)
        EXCHANGES.find do |exchange|
          exchange.method == method && without_query(exchange.path) == path
        end
      end

      # Returns the contract answer for one concrete request.
      def respond(method, target, request_body = nil)
        exchange = exchange_for(method, target)
        return Response.new(status: 404, body: '{"message": "no such route"}') unless exchange

        Response.new(
          status: exchange.status,
          body: exchange.render_response_body(request_body)
        )
      end

      # Sends the measured exchanges through the caller's HTTP library.
      def drive(base_url = mock_server_url, sender = nil, &block)
        raise ArgumentError, "base URL must not be blank" if blank?(base_url)

        send_request = sender || block
        raise ArgumentError, "sender must be supplied" unless send_request

        normalized_base_url = base_url.sub(%r{/+\z}, "")
        REQUESTS.each do |exchange|
          response = send_request.call(
            exchange.method,
            "#{normalized_base_url}#{exchange.path}",
            exchange.body
          )
          puts "#{exchange.method} #{exchange.path} -> #{response.status} #{abbreviate(response.body)}"
          verify(exchange, response)
        end
        nil
      end

      # Checks an exact status and a response body by JSON structure.
      def verify(exchange, response)
        where = "#{exchange.method} #{exchange.path}"
        if response.status != exchange.status
          raise ContractError,
                "#{where} answered #{response.status}, but the contract's request answers #{exchange.status}"
        end

        expected = parse_json(exchange.render_response_body(exchange.body))
        actual = parse_json(response.body)
        return nil if actual == expected

        raise ContractError,
              "#{where} answered #{JSON.generate(actual)}, but the contract's request answers #{JSON.generate(expected)}"
      end

      # Headers shared by client workloads.
      def client_headers(body)
        headers = { "User-Agent" => USER_AGENT }
        headers["Content-Type"] = CONTENT_TYPE unless body.nil?
        headers
      end

      # The mock server URL supplied to a client scenario.
      def mock_server_url
        value = ENV[MOCK_SERVER_URL_VARIABLE]
        return value unless blank?(value)

        raise ConfigurationError,
              "#{MOCK_SERVER_URL_VARIABLE} is not set; the runner publishes it for the configured server"
      end

      # The port supplied to a server scenario.
      def scenario_port
        value = ENV[PORT_VARIABLE]
        if blank?(value)
          raise ConfigurationError,
                "#{PORT_VARIABLE} is not set; otel-http-drive chooses the port"
        end

        port = Integer(value, 10)
        return port if port.between?(1, 65_535)

        raise ConfigurationError, "#{PORT_VARIABLE} is not a valid port: #{value}"
      rescue ArgumentError
        raise ConfigurationError, "#{PORT_VARIABLE} is not a valid port: #{value}"
      end

      def without_query(target)
        target.split("?", 2).first
      end
      private_class_method :without_query

      def parse_json(value)
        JSON.parse(value)
      rescue JSON::ParserError => error
        raise ContractError, "not JSON: #{value}", error.backtrace
      end
      private_class_method :parse_json

      def blank?(value)
        value.nil? || value.strip.empty?
      end
      private_class_method :blank?

      def abbreviate(value)
        value.to_s.tr("\r\n", "  ")[0, 60]
      end
      private_class_method :abbreviate
    end
  end
end
