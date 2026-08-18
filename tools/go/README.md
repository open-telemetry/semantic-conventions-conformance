# Go conformance scenarios

Everything a Go scenario shares: the support every scenario needs whatever
domain it measures, and the command that builds and runs one.

```text
scenarios/<domain>/go/    a domain's Go module — the scenarios and their pins
tools/go/scenario/        what a scenario needs before any telemetry
tools/go/scenariosdk/     the SDK a library-instrumentation scenario owns
tools/go/src/             `otel-conformance-go`, the launcher
tools/go/tests/           the launcher's tests
```

## A module per domain

A domain's Go scenarios are one module, rooted at its own `scenarios/<domain>/go`
— today only [`scenarios/http/go`](../../scenarios/http/go). That module pins
the instrumentation versions its scenarios are measured at, and reaches the
projects here through `replace` directives, so nothing under `tools/` has to be
published before a scenario can use it.

One module for a whole domain rather than one per scenario: Go links only what
a binary imports, so two instrumentations sharing a module do not end up in
each other's builds.

## What a scenario shares

[`scenario/`](scenario) carries no OpenTelemetry dependency at all. An
out-of-process agent — eBPF, for Go — measures a binary that asked for no SDK,
so what every scenario needs regardless, the runner's environment and the
driver's shutdown protocol, is kept where such a scenario can reach it.

[`scenariosdk/`](scenariosdk) is the other half: the OTLP exporters over gRPC,
the providers installed globally where instrumentation libraries look for them,
and the flush that runs before the process exits. Go has no SDK
autoconfiguration package, so this wiring is written down once rather than in
each scenario.

Go's linker keeps whatever the import graph reaches, and an imported package is
initialized even when nothing calls it, so the package boundary is what holds
the exporters out: a binary importing only `scenario` links no SDK and no gRPC,
while one package holding both would link both. The two halves ship in one
module, because it is the import that decides this and not the module.

## `otel-conformance-go`

Builds and runs a Go conformance scenario, so no `conformance.yaml` restates
how Go is built.

```yaml
setup: otel-conformance-go build

scenarios:
  server:
    run: otel-http-drive --serve otel-conformance-go run
```

Neither subcommand takes a package: a Go scenario's package *is* its directory,
and the runner runs both phases there.

`build` compiles into `build/` beside the scenario, ahead of the measured run,
so no toolchain is on the clock. `run` executes the result by absolute path,
which is what the launcher is for: Windows resolves a relative command against
the calling process's directory rather than the working directory it is given,
and needs an `.exe` suffix that no other platform wants. A scenario file naming
the binary itself would only run on the platform it was written on.
