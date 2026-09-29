# PHP conformance tools

PHP scenarios share two small pieces.

`scenario/` is a Composer package with required environment lookup. It has no
OpenTelemetry dependency, so a scenario only loads the telemetry packages it
declares.

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

`relock` is for maintainers: from anywhere in the repository, it runs
`composer update --no-install --no-scripts --minimal-changes` for every
committed `composer.lock` under `scenarios/` and `tools/`. That rewrites the
lock only, and changes nothing the manifests don't require. A lock records a
path package's `dist.reference`, a hash of that package's `composer.json`, so
editing `scenario/` or the HTTP test client's `composer.json` leaves the locks
that depend on it stale. `composer install` does not notice this. CI runs
`relock` on Renovate PRs and commits the result. CI pins the Composer version,
because Composer stamps its plugin API version into every lock. Use the same
Composer version when running it by hand:

```sh
otel-conformance-php relock
```

Run the launcher tests with:

```sh
python -m pytest tools/php/tests
```

Run the Composer support tests with:

```sh
composer --working-dir tools/php/scenario install
composer --working-dir tools/php/scenario test
```
