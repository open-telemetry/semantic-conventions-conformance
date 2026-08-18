# .NET HTTP conformance scenarios

Two packages: an ASP.NET Core server and a `System.Net.Http.HttpClient` client,
each measured with the OpenTelemetry instrumentation written for it.

On .NET 10 those instrumentations are mostly subscriptions rather than
implementations. `System.Net.Http` and ASP.NET Core emit the spans and metrics
themselves, and a package here turns that on and exports it. So a divergence a
scenario records is usually the platform's to close rather than the package's,
and its `conformance.yaml` says which.

```text
aspnetcore/scenarios/                    what the server does, no OTel
aspnetcore/opentelemetry-aspnetcore/     the launcher, and server/
httpclient/scenarios/                    what the client does, no OTel
httpclient/opentelemetry-http/           the launcher, and client/
```

[`http-dotnet-conformance.slnx`](http-dotnet-conformance.slnx) is the build
root. It lists the shared projects under [`tools/`](../../../tools) alongside
these four rather than restating them, so `dotnet build` here builds and tests
everything a .NET HTTP scenario depends on.

## What the launchers add

A .NET instrumentation is a package the SDK subscribes through, not a decorator
a scenario wraps its client or server in:

```csharp
using var sdk = ScenarioSdk.Initialize(
    tracing => tracing.AddHttpClientInstrumentation(),
    metrics => metrics.AddHttpClientInstrumentation());
```

So unlike a framework instrumented by decoration, the workload projects here
have nothing to hand their launcher — they are plain, and the launcher's whole
job is to build the SDK before the workload starts. They stay separate projects
anyway, because that is what keeps the instrumentation packages out of the
workload and lets a second instrumentation of the same library measure the same
program.

The server declares its routes as ASP.NET Core minimal APIs, because that
declaration is what the instrumentation reports `http.route` from:

```csharp
app.MapGet("/users/{userId}", AnswerAsync);
```

`/users/123` arrives, `GET /users/{userId}` is recorded. Answering is a lookup
of the concrete request in the shared
[contract](../../../tools/http/test-client/contract.json), identical for every
framework, so a route here says only what its template is.

## Versions

[`Directory.Packages.props`](Directory.Packages.props) pins the instrumentation
releases both packages measure, so a client and a server can never report
coverage from two different releases. The SDK they export through is pinned in
[`tools/dotnet`](../../../tools/dotnet) instead, because MSBuild resolves those
pins per directory tree and `tools/` is outside this one.

## Running one

```sh
otel-conformance scenarios/http/dotnet/aspnetcore/opentelemetry-aspnetcore/server
otel-conformance scenarios/http/dotnet/httpclient/opentelemetry-http/client
```

A package's `setup:` is `otel-conformance-dotnet build` and its `run:` is
`otel-conformance-dotnet run`, so the launcher publishes the project the
scenario directory belongs to and then starts what it published. The measured
process is the scenario and not a toolchain wrapper that would restore and
compile on the clock. See [`tools/dotnet`](../../../tools/dotnet).
