// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

namespace OpenTelemetry.Conformance.Scenario;

/// <summary>The OpenTelemetry SDK a scenario configures for itself.</summary>
/// <remarks>
/// Only a scenario measuring explicit library instrumentation needs this. A scenario measuring the
/// .NET automatic instrumentation has its SDK loaded into the process for it, and must not carry
/// these packages at all.
/// <para>
/// Both signals are built here because a scenario is measured on both: a client or server span and
/// the duration metric beside it come from the same instrumentation, so a scenario that configured
/// only tracing would record half of what it emitted.
/// </para>
/// </remarks>
public sealed class ScenarioSdk : IDisposable
{
    private const int FlushTimeoutMilliseconds = 30_000;

    private readonly TracerProvider tracerProvider;
    private readonly MeterProvider meterProvider;

    private ScenarioSdk(TracerProvider tracerProvider, MeterProvider meterProvider)
    {
        this.tracerProvider = tracerProvider;
        this.meterProvider = meterProvider;
    }

    /// <summary>
    /// Builds the SDK with the instrumentation a scenario adds, failing early rather than
    /// exporting nowhere.
    /// </summary>
    /// <remarks>
    /// The exporter and the resource are read from the environment the runner injected, so nothing
    /// about where a run exports to appears in a scenario. What a scenario passes is only the
    /// instrumentation under test.
    /// </remarks>
    public static ScenarioSdk Initialize(
        Action<TracerProviderBuilder> configureTracing,
        Action<MeterProviderBuilder> configureMetrics)
    {
        ArgumentNullException.ThrowIfNull(configureTracing);
        ArgumentNullException.ThrowIfNull(configureMetrics);
        ScenarioEnvironment.Require("OTEL_EXPORTER_OTLP_ENDPOINT");

        var tracing = Sdk.CreateTracerProviderBuilder();
        configureTracing(tracing);
        var metrics = Sdk.CreateMeterProviderBuilder();
        configureMetrics(metrics);

        return new ScenarioSdk(
            Built(tracing.AddOtlpExporter().Build(), "tracer"),
            Built(metrics.AddOtlpExporter().Build(), "meter"));
    }

    /// <summary>Flushes what the scenario emitted, then shuts the SDK down.</summary>
    /// <remarks>
    /// The flush is explicit rather than left to the providers' own shutdown because the runner
    /// sets an effectively infinite metric export interval: without it a scenario's metrics would
    /// never leave the process.
    /// </remarks>
    public void Dispose()
    {
        this.tracerProvider.ForceFlush(FlushTimeoutMilliseconds);
        this.meterProvider.ForceFlush(FlushTimeoutMilliseconds);
        this.tracerProvider.Dispose();
        this.meterProvider.Dispose();
    }

    private static T Built<T>(T? provider, string what)
        where T : class =>
        provider ?? throw new InvalidOperationException(
            $"the OpenTelemetry SDK built no {what} provider");
}
