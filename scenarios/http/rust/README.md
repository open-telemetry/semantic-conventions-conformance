# Rust HTTP conformance scenarios

`scenarios/http/rust` is one Cargo workspace for the HTTP domain. Its committed
`Cargo.lock` pins the framework, instrumentation, OpenTelemetry SDK, and shared
Rust crates that every package in this domain builds against.

```text
actix-web/scenarios/                           plain Actix Web server workload
actix-web/opentelemetry-actix-web/server/      traced and measured server binary
awc/scenarios/                                 plain awc client workload
awc/opentelemetry-actix-web/client/            traced client binary
tower/scenarios/                               plain Tower HTTP server workload
tower/opentelemetry-instrumentation-tower/server/ traced and measured server binary
../../../tools/http/test-client/rust/          shared HTTP contract
../../../tools/rust/scenario/                  environment and shutdown protocol
../../../tools/rust/scenario-sdk/              OTLP gRPC SDK bootstrap
```

The workload crates import no OpenTelemetry code. The Actix Web binary crates
add `opentelemetry-instrumentation-actix-web`: `RequestTracing` and
`RequestMetrics` wrap the server, while the crate's `awc` feature traces each
client request. The Tower binary wraps a plain Tower service with
`opentelemetry-instrumentation-tower` and uses Hyper only for HTTP transport.
It has no router-provided route metadata, so server spans have method-only
names and no `http.route`. Both server instrumentations emit the standard
HTTP server metrics.

The Tower instrumentation emits an empty `url.scheme` for the origin-form
request targets received by Hyper.

Client and server remain separate conformance packages and coverage files.
Combining them would let one side's telemetry hide a missing signal from the
other, even though one instrumentation crate covers both.

`otel-conformance-rust build` compiles the package containing the current
scenario directory in release mode. `otel-conformance-rust run` then executes
that package's binary by absolute path, including the Windows `.exe` suffix.
Cargo is therefore never the measured process's parent.

Run all Rust checks from this directory:

```sh
cargo fmt --check
cargo clippy --workspace -- -D warnings
cargo test --workspace
```
