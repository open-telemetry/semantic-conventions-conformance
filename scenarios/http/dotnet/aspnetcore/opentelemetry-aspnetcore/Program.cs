// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using OpenTelemetry.Conformance.Http.AspNetCore;
using OpenTelemetry.Conformance.Scenario;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

// ASP.NET Core 11+ emits OpenTelemetry HTTP server spans and metrics itself, so there is no
// instrumentation package to add: the SDK only has to listen to what the platform already emits.
// It is built before the workload starts, because ASP.NET Core only records a request when a
// provider is already listening to its ActivitySource and its meters.
using var sdk = ScenarioSdk.Initialize(
    // The hosting activity source carries the HTTP server spans.
    tracing => tracing.AddSource("Microsoft.AspNetCore"),
    // The hosting meter carries the HTTP server metrics. Kestrel, routing and memory-pool metrics
    // are ASP.NET Core's own, not HTTP's, so their meters are left unsubscribed.
    metrics => metrics.AddMeter("Microsoft.AspNetCore.Hosting"));

await AspNetCoreServerScenario.RunAsync().ConfigureAwait(false);
