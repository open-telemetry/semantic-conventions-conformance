# PHP HTTP conformance test client

This Composer package decodes the HTTP actions supplied by the runner.
`ServerWorkload::respond()` supplies the exact status and body for a request.
`ClientWorkload::drive()` sends the runner-selected request through a
caller-supplied function.

Client processes read `OTEL_CONFORMANCE_SCENARIO_ACTION`. Server processes read
`OTEL_CONFORMANCE_SCENARIO_ACTIONS` once and use it for every route lookup.

Run its unit tests with:

```sh
composer install
composer test
```
