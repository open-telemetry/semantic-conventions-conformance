# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "net/http"
require "uri"
require "opentelemetry/conformance/http"

module NetHttpScenario
  HTTPContract = OpenTelemetry::Conformance::HTTP

  # Sends the shared HTTP contract over one persistent Net::HTTP connection.
  class Client
    def initialize(base_url, http_class: Net::HTTP)
      @base_url = base_url
      base_uri = URI(base_url)
      @connection = http_class.new(base_uri.host, base_uri.port)
      @connection.use_ssl = base_uri.scheme == "https"
    end

    def run
      @connection.start do
        HTTPContract.drive(@base_url) do |method, url, body|
          request(method, url, body)
        end
      end
    end

    def request(method, url, body)
      request_uri = URI(url).request_uri
      net_request = Net::HTTPGenericRequest.new(
        method,
        !body.nil?,
        true,
        request_uri,
        HTTPContract.client_headers(body)
      )
      net_request.body = body unless body.nil?

      response = @connection.request(net_request)
      HTTPContract::Response.new(
        status: response.code.to_i,
        body: response.body.to_s
      )
    end
  end

  module_function

  def run(base_url = HTTPContract.mock_server_url, http_class: Net::HTTP)
    Client.new(base_url, http_class: http_class).run
  end
end
