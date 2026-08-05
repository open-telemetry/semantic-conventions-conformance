# HTTP OpenTelemetry Conformance

Automated conformance validation of HTTP client and server instrumentations
against the [OpenTelemetry Semantic Conventions for HTTP](https://opentelemetry.io/docs/specs/semconv/http/).

See the [root README](../README.md) for an overview of
[how the pipeline works](../README.md#how-it-works).

## Scenarios

Each scenario lives at `<language>/<library>/` and commits the coverage it
produces as `data-<ecosystem>.json`. Today that is Python / Flask on OTel
Contrib; more libraries and languages are being migrated in, tracked in
[#6](https://github.com/open-telemetry/semantic-conventions-conformance/issues/6).

## Contributing

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for local setup, how to run a
single scenario, and how to add a new library or ecosystem.
