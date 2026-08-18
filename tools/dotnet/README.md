# .NET conformance scenarios

Everything a .NET scenario shares: the support every scenario needs whatever
domain it measures, and the SDK the ones measuring library instrumentation
build for themselves.

```text
scenarios/<domain>/dotnet/                   a domain's build root — the solution and its pins
tools/dotnet/OpenTelemetry.Conformance.Scenario/      what a scenario needs before any telemetry
tools/dotnet/OpenTelemetry.Conformance.Scenario.Sdk/  the SDK a library-instrumentation scenario owns
tools/dotnet/src/                            `otel-conformance-dotnet`, the launcher
tools/dotnet/tests/                          the launcher's tests
```

## A build root per domain

A domain's .NET scenarios are one solution, rooted at its own
`scenarios/<domain>/dotnet` — today only
[`scenarios/http/dotnet`](../../scenarios/http/dotnet). It lists the projects
here rather than restating them, so `dotnet build` at a build root is the whole
language's build and a shared project cannot drift out of date behind a
domain's back.

What is not shared is the pins. MSBuild resolves `Directory.Packages.props` by
walking up from each project, and `tools/` is not under any build root, so the
projects here read [`Directory.Packages.props`](Directory.Packages.props) beside
them while a domain's scenarios read their own. The SDK release is therefore
pinned once for every domain, and the instrumentation releases a domain measures
are pinned with that domain. [`Directory.Build.props`](Directory.Build.props)
carries the settings that are not versions, and a build root imports it.

## What a scenario shares

[`OpenTelemetry.Conformance.Scenario`](OpenTelemetry.Conformance.Scenario)
carries no OpenTelemetry dependency at all, which is the point: .NET's automatic
instrumentation injects its own SDK into the process through the CLR profiler,
so a scenario measuring it must not carry SDK packages of its own. What every
scenario needs — the runner's environment, and the driver's shutdown protocol —
therefore cannot live beside the SDK.

`ScenarioLifecycle.WaitForEofAsync` is that shutdown protocol: a server scenario
serves until its standard input closes. Standard input rather than a signal,
because it is the one mechanism that behaves the same on Windows, and rather
than a shutdown route, because a route would show up as coverage the scenario
never meant to record.

[`OpenTelemetry.Conformance.Scenario.Sdk`](OpenTelemetry.Conformance.Scenario.Sdk)
is the other half: the tracer and meter providers, the OTLP exporter, and the
flush, for scenarios measuring explicit library instrumentation. A scenario
passes only the instrumentation under test:

```csharp
using var sdk = ScenarioSdk.Initialize(
    tracing => tracing.AddAspNetCoreInstrumentation(),
    metrics => metrics.AddAspNetCoreInstrumentation());
```

The flush is explicit rather than left to the providers' own shutdown, because
the runner sets an effectively infinite metric export interval so that a run
reads one deliberate export rather than whatever the interval happened to catch.

Both projects share the `OpenTelemetry.Conformance.Scenario` namespace: a
namespace ending in `Sdk` would shadow `OpenTelemetry.Sdk` in every file that
built a provider.

## `otel-conformance-dotnet`

Builds and runs a .NET conformance scenario, so no `conformance.yaml` restates
how .NET is built:

```yaml
setup: otel-conformance-dotnet build

scenarios:
  server:
    run: otel-http-drive --serve otel-conformance-dotnet run
```

Neither subcommand takes an argument. A scenario directory sits inside the
project that produces it, so the project is the nearest `.csproj` at or above
the directory the command runs in, and the build root is the nearest
`Directory.Build.props` above that — the file that declares `PublishDir`, found
the way MSBuild itself resolves it.

`build` publishes that project. `run` starts what it published, from the build
root's `build/scenario-runtime/<project>`, so a scenario file names neither a
configuration nor an output path and a change to either is the build's to make.

`run` executes `dotnet <assembly>` rather than the published launcher
executable, whose name is `.exe` on Windows and extensionless everywhere else,
so one `conformance.yaml` runs on either. That is the only reason: .NET has no
build daemon whose older environment a measured run could inherit. Everything
after `run` reaches the scenario verbatim, including arguments that begin with
`-`.
