# PHP conformance tools

PHP scenarios share two small pieces.

`scenario/` is a Composer package with required environment lookup and the
standard-input end-of-file shutdown protocol. It has no OpenTelemetry
dependency, so a scenario only loads the telemetry packages it declares.

`otel-conformance-php` is a standard-library-only Python command used by
`conformance.yaml`:

```yaml
setup: otel-conformance-php install

scenarios:
  server:
    run: otel-http-drive --serve otel-conformance-php serve ../router.php
```

`install` searches upward from the scenario directory for the nearest
`composer.json` and runs Composer there. This keeps each instrumentation side
as its own locked package and also resolves `composer.bat` on Windows.

`serve` starts `php -S 127.0.0.1:$OTEL_HTTP_SCENARIO_PORT <router>`. The PHP
built-in server keeps the normal request-scoped lifecycle used by PHP-FPM:
Composer and the OpenTelemetry SDK initialize for each request, then shutdown
handlers flush that request's telemetry. The Python parent owns the driver's
standard-input protocol and stops the server when the driver closes it.

Run the launcher tests with:

```sh
python -m pytest tools/php/tests
```

Run the Composer support tests with:

```sh
composer --working-dir tools/php/scenario install
composer --working-dir tools/php/scenario test
```
