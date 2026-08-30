# PHP HTTP conformance scenarios

PHP measures a Slim 4 server through
`open-telemetry/opentelemetry-auto-slim` and a Guzzle 7 client through
`open-telemetry/opentelemetry-auto-guzzle`.

```text
slim/scenarios/                       Slim routes and responses, no OTel
slim/opentelemetry-slim/              locked instrumentation package
guzzle/scenarios/                     Guzzle request workload, no OTel
guzzle/opentelemetry-guzzle/          locked instrumentation package
```

Each instrumentation side is its own Composer package with its own committed
`composer.lock`. This keeps the measured dependency graph exact without
creating a PHP-wide build root. Both use the path package from
[`tools/http/test-client/php`](../../../tools/http/test-client/php), and
Guzzle also uses [`tools/php/scenario`](../../../tools/php/scenario) to read
the mock server's URL.

PHP auto-instrumentation needs the `opentelemetry` extension and
`OTEL_PHP_AUTOLOAD_ENABLED=true`. OTLP uses gRPC because Weaver live-check
receives OTLP gRPC, so the runtime also needs the `grpc` and `protobuf`
extensions.

The measured releases emit stable HTTP attributes by default. Real runs of
both packages therefore need no `OTEL_SEMCONV_STABILITY_OPT_IN`.

## Request-scoped server lifecycle

The Slim scenario runs under PHP's built-in server rather than a long-lived
event loop. Like PHP-FPM, `php -S` loads Composer and the OpenTelemetry SDK in
each request and runs shutdown handlers when that request finishes. Each
request therefore flushes its telemetry through the SDK lifecycle PHP users
actually run.

`otel-conformance-php serve` is the parent process. It starts the built-in
server on the port chosen by `otel-http-drive`, relays its output, and stops it
when the driver closes standard input. The workload itself stays ordinary Slim
routing code.

## Running

Install PHP 8.2 or later, Composer, and the `opentelemetry`, `grpc`, and
`protobuf` extensions. Then install the Python runner commands and run either
side:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/php
otel-conformance scenarios/http/php/slim/opentelemetry-slim/server
otel-conformance scenarios/http/php/guzzle/opentelemetry-guzzle/client
```
