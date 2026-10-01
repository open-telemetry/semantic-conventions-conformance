# HTTP conformance contract for Ruby

This local gem reads the shared [HTTP contract](../README.md). It has no runtime dependencies outside Ruby's standard library.

Add it to a scenario Gemfile:

```ruby
gem "opentelemetry-conformance-http",
    path: "../../../../../../tools/http/test-client/ruby"
```

Require it as `opentelemetry/conformance/http`:

```ruby
require "opentelemetry/conformance/http"

HTTPContract = OpenTelemetry::Conformance::HTTP
```

## Client scenarios

`drive` sends only measured requests. The sender must return an `HTTPContract::Response`:

```ruby
HTTPContract.drive(HTTPContract.mock_server_url) do |method, url, body|
  headers = HTTPContract.client_headers(body)
  response = client.send(method, url, body, headers)
  HTTPContract::Response.new(status: response.status, body: response.body)
end
```

The helper checks the exact status and compares parsed JSON bodies. The runner starts the mock server before a client scenario, so `drive` does not send a readiness request.

## Server scenarios

Bind the framework server to `HTTPContract.scenario_port`. Framework routes call `respond` with the concrete request:

```ruby
answer = HTTPContract.respond(request_method, request_target, request_body)
framework_response(answer.status, HTTPContract::CONTENT_TYPE, answer.body)
```

Route declarations stay in each framework. `respond` ignores the query when finding an exchange, substitutes the received body where the contract requests it, and returns a 404 response for unknown traffic.
