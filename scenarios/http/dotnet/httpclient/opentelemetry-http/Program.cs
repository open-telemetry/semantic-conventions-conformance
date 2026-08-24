// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using OpenTelemetry.Conformance.Http.SystemNetHttp;
using OpenTelemetry.Conformance.Scenario;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

// The SDK is built before the workload starts, because System.Net.Http only records a request when
// a provider is already listening to its ActivitySource and its meters.
using var sdk = ScenarioSdk.Initialize(
    tracing => tracing.AddHttpClientInstrumentation(),
    metrics => metrics.AddHttpClientInstrumentation());

await HttpClientScenario.RunAsync().ConfigureAwait(false);
