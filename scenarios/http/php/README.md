# PHP HTTP conformance scenarios

PHP measures these HTTP libraries and frameworks through their published
auto-instrumentation packages.

| Scenario | Side | Instrumentation |
| --- | --- | --- |
| CakePHP | server | `open-telemetry/opentelemetry-auto-cakephp` |
| CodeIgniter | server | `open-telemetry/opentelemetry-auto-codeigniter` |
| curl | client | `open-telemetry/opentelemetry-auto-curl` |
| Guzzle | client | `open-telemetry/opentelemetry-auto-guzzle` |
| Laravel | server | `open-telemetry/opentelemetry-auto-laravel` |
| PSR-15 | server | `open-telemetry/opentelemetry-auto-psr15` |
| PSR-18 | client | `open-telemetry/opentelemetry-auto-psr18` |
| ReactPHP | client | `open-telemetry/opentelemetry-auto-reactphp` |
| Slim | server | `open-telemetry/opentelemetry-auto-slim` |
| Symfony | server | `open-telemetry/opentelemetry-auto-symfony` |
| Symfony HTTP Client | client | `open-telemetry/opentelemetry-auto-symfony` |
| WordPress | server | `open-telemetry/opentelemetry-auto-wordpress` |
| Yii | server | `open-telemetry/opentelemetry-auto-yii` |

Each instrumentation side is its own Composer package with its own committed
`composer.lock`. This keeps the measured dependency graph exact without
creating a PHP-wide build root. All packages use the path dependency from
[`tools/http/test-client/php`](../../../tools/http/test-client/php). All except
Slim also use [`tools/php/scenario`](../../../tools/php/scenario) to read
runtime configuration such as the mock server's URL.

PHP auto-instrumentation needs the `opentelemetry` extension and
`OTEL_PHP_AUTOLOAD_ENABLED=true`. OTLP uses gRPC because Weaver live-check
receives OTLP gRPC, so the runtime also needs the `grpc` and `protobuf`
extensions. CodeIgniter needs `intl`, curl needs `curl`, and the self-contained
WordPress fixture uses `pdo_sqlite`.

The measured releases emit stable HTTP attributes by default. Runs therefore
need no `OTEL_SEMCONV_STABILITY_OPT_IN`.

## Request-scoped server lifecycle

Server scenarios run under PHP's built-in server rather than a long-lived event
loop. Like PHP-FPM, `php -S` loads Composer and the OpenTelemetry SDK in each
request and runs shutdown handlers when that request finishes. Each request
therefore flushes its telemetry through the SDK lifecycle PHP users run.

`otel-conformance-php serve` is the parent process. It starts the built-in
server on the port chosen by `otel-http-drive`, lets `php -S` inherit the
launcher's standard output and standard error, and stops it when the driver
closes standard input. The workload itself stays ordinary
framework or PSR code.

CodeIgniter copies its pinned framework app skeleton into an ignored runtime
directory during Composer install, then overlays the committed routes and
controller. WordPress installs its pinned core and SQLite drop-in through
Composer, creates its local database once, and loads a must-use plugin that
answers the shared contract after `WP::main()` runs. Neither fixture needs an
external service.

## Running

Install PHP 8.4, Composer, and the extensions listed above. Then install the
Python runner commands and run any package:

```sh
pip install -e tools/runner -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/php
otel-conformance scenarios/http/php/slim/opentelemetry-slim/server
otel-conformance scenarios/http/php/guzzle/opentelemetry-guzzle/client
otel-conformance scenarios/http/php/cakephp/opentelemetry-cakephp/server
otel-conformance scenarios/http/php/symfony-http-client/opentelemetry-symfony/client
```
