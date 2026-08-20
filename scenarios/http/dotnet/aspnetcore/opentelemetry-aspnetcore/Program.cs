// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using OpenTelemetry.Conformance.Http.AspNetCore;
using OpenTelemetry.Conformance.Scenario;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

// The SDK is built before the workload starts, because ASP.NET Core only records a request when a
// provider is already listening to its ActivitySource and its meters.
using var sdk = ScenarioSdk.Initialize(
    tracing => tracing.AddAspNetCoreInstrumentation(),
    // AddAspNetCoreInstrumentation() would report Kestrel, routing and memory-pool metrics too:
    // it instruments ASP.NET Core, not HTTP. The hosting meter carries the HTTP server metrics.
    metrics => metrics.AddMeter("Microsoft.AspNetCore.Hosting"));

await AspNetCoreServerScenario.RunAsync().ConfigureAwait(false);
