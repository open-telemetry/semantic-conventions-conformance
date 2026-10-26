# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "rack"
require "rackup/handler/webrick"
require "opentelemetry/conformance/http"
require "opentelemetry/conformance/scenario_support"

module RackServerScenario
  HTTP = OpenTelemetry::Conformance::HTTP
  ROUTES = [
    "/health",
    "/users/123",
    "/items",
    "/status/404",
    "/status/500"
  ].freeze

  class Endpoint
    def call(environment)
      request = Rack::Request.new(environment)
      body = request.post? ? request.body.read : nil
      response = HTTP.respond(request.request_method, request.fullpath, body)
      payload = response.body

      [
        response.status,
        {
          "content-type" => HTTP::CONTENT_TYPE,
          "content-length" => payload.bytesize.to_s
        },
        [payload]
      ]
    end
  end

  module_function

  def application
    Rack::Builder.new do
      ROUTES.each do |path|
        map(path) { run Endpoint.new }
      end
      run Endpoint.new
    end
  end

  def serve(app, input: $stdin, port: HTTP.scenario_port)
    ready = Queue.new
    server_thread = Thread.new do
      Rackup::Handler::WEBrick.run(
        app,
        Host: "127.0.0.1",
        Port: port,
        AccessLog: [],
        Logger: WEBrick::Log.new($stderr, WEBrick::Log::WARN)
      ) do |server|
        ready << [:ready, server]
      end
    rescue StandardError => error
      ready << [:error, error]
    end

    state, server = ready.pop
    raise server if state == :error

    OpenTelemetry::Conformance::ScenarioLifecycle.wait_for_eof(input)
  ensure
    server&.shutdown if state == :ready
    server_thread&.join
  end
end
