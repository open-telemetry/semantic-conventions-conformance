# Rust conformance scenarios

Everything Rust scenarios share lives here:

```text
scenario/       required environment lookup and stdin-EOF shutdown, no OTel
scenario-sdk/   global trace and metric providers with OTLP gRPC exporters
src/            the `otel-conformance-rust` build and run command
tests/          launcher tests
```

Each domain owns one Cargo workspace and lockfile. The workspace includes these
shared crates as members, so one root build, Clippy run, and test run covers the
scenario binaries and all Rust support they use.

Rust has no SDK autoconfiguration crate. `scenario-sdk` therefore requires the
collector endpoint, creates tonic gRPC trace and metric exporters, installs the
providers globally for instrumentation libraries, and shuts both down after
the workload ends.

A conformance package needs no launcher arguments:

```yaml
setup: otel-conformance-rust build

scenarios:
  server:
    run: otel-http-drive --serve otel-conformance-rust run
```

The launcher searches upward for both the package and workspace manifests.
`build` compiles only that package in release mode. `run` starts the resulting
absolute binary path, adding `.exe` on Windows, so Cargo is not part of the
measured process tree.
