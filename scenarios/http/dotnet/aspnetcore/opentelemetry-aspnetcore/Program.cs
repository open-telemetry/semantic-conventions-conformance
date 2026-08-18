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
    // AddAspNetCoreInstrumentation() listens to every built-in ASP.NET Core meter, because the
    // package instruments the framework rather than HTTP alone, and a run then reports Kestrel,
    // routing and memory-pool metrics beside the ones under test. The hosting meter is the one
    // carrying the HTTP server metrics, so listening to it alone keeps this report about HTTP.
    metrics => metrics.AddMeter("Microsoft.AspNetCore.Hosting"));

await AspNetCoreServerScenario.RunAsync().ConfigureAwait(false);
