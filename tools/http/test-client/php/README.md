# PHP HTTP conformance test client

This Composer package reads the one
[`contract.json`](../contract.json) shared by every HTTP scenario.
`ServerWorkload::respond()` supplies the exact status and body for a request.
`ClientWorkload::drive()` sends every measured request through a caller-supplied
function and verifies each response as parsed JSON.

The package locates the contract beside its source checkout first. When
Composer installs it as a copied path dependency, it walks up from the
scenario directory to the repository copy. `OTEL_HTTP_CONTRACT` is the
explicit override for running away from a checkout.

Run its unit tests with:

```sh
composer install
composer test
```
