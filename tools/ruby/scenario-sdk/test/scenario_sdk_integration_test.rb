# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "minitest/autorun"
require "open3"
require "rbconfig"
require "socket"
require "opentelemetry-exporter-otlp-metrics"

class ScenarioSdkIntegrationTest < Minitest::Test
  ExportMetricsServiceRequest =
    Opentelemetry::Proto::Collector::Metrics::V1::ExportMetricsServiceRequest
  ExportMetricsServiceResponse =
    Opentelemetry::Proto::Collector::Metrics::V1::ExportMetricsServiceResponse

  SCENARIO_SDK_LIB = File.expand_path("../lib", __dir__)
  CHILD_PROGRAM = <<~RUBY
    require "opentelemetry/instrumentation/net/http"
    require "opentelemetry/conformance/scenario_sdk"

    OpenTelemetry::Conformance::ScenarioSdk.run(
      instrumentation: "OpenTelemetry::Instrumentation::Net::HTTP"
    ) do
      meter = OpenTelemetry.meter_provider.meter("conformance.pipeline.test")
      histogram = meter.create_histogram(
        "conformance.pipeline.duration",
        unit: "s"
      )
      histogram.record(1.25, attributes: { "test.case" => "explicit" })
    end
  RUBY

  def test_explicit_histogram_reaches_the_otlp_metrics_exporter
    requests, stdout, stderr, status = capture_exports

    assert status.success?, <<~MESSAGE
      child process failed with #{status.exitstatus}
      stdout:
      #{stdout}
      stderr:
      #{stderr}
    MESSAGE

    metric_requests =
      requests
        .select { |request| request.fetch(:path) == "/v1/metrics" }
        .map do |request|
          assert_equal "POST", request.fetch(:method)
          assert_equal "application/x-protobuf",
                       request.fetch(:headers).fetch("content-type")
          ExportMetricsServiceRequest.decode(request.fetch(:body))
        end
    refute_empty metric_requests

    metrics =
      metric_requests.flat_map do |request|
        request.resource_metrics.flat_map do |resource_metrics|
          resource_metrics.scope_metrics.flat_map(&:metrics)
        end
      end
    histogram =
      metrics.find { |metric| metric.name == "conformance.pipeline.duration" }

    refute_nil histogram
    data_point = histogram.histogram.data_points.fetch(0)
    assert_equal 1, data_point.count
    assert_in_delta 1.25, data_point.sum
  end

  private

  def capture_exports
    server = TCPServer.new("127.0.0.1", 0)
    requests = []
    server_thread = Thread.new { serve_exports(server, requests) }
    endpoint = "http://127.0.0.1:#{server.local_address.ip_port}"
    env = {
      "OTEL_EXPORTER_OTLP_ENDPOINT" => endpoint,
      "OTEL_EXPORTER_OTLP_COMPRESSION" => "none",
      "OTEL_METRIC_EXPORT_INTERVAL" => (2**31 - 1).to_s
    }

    stdout, stderr, status =
      Open3.capture3(
        env,
        RbConfig.ruby,
        "-I#{SCENARIO_SDK_LIB}",
        "-e",
        CHILD_PROGRAM
      )
    [requests, stdout, stderr, status]
  ensure
    server&.close
    server_thread&.join
  end

  def serve_exports(server, requests)
    loop do
      client = server.accept
      requests << read_request(client)
      response = ExportMetricsServiceResponse.encode(
        ExportMetricsServiceResponse.new
      )
      client.write(
        "HTTP/1.1 200 OK\r\n" \
        "Content-Type: application/x-protobuf\r\n" \
        "Content-Length: #{response.bytesize}\r\n" \
        "Connection: close\r\n\r\n" \
        "#{response}"
      )
      client.close
    end
  rescue IOError, Errno::EBADF
    nil
  end

  def read_request(client)
    method, path, = client.gets("\r\n").split
    headers = {}
    while (line = client.gets("\r\n")) != "\r\n"
      name, value = line.split(":", 2)
      headers[name.downcase] = value.strip
    end
    length = Integer(headers.fetch("content-length"), 10)
    {
      method: method,
      path: path,
      headers: headers,
      body: client.read(length)
    }
  end
end
