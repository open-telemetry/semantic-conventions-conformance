// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Diagnostics;
using OpenTelemetry.Logs;
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
    private const int TotalFlushTimeoutMilliseconds = 15_000;

    private readonly OpenTelemetrySdk sdk;

    private ScenarioSdk(OpenTelemetrySdk sdk)
    {
        this.sdk = sdk;
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

        return new ScenarioSdk(OpenTelemetrySdk.Create(builder => builder
            .WithTracing(tracing =>
            {
                configureTracing(tracing);
                tracing.AddOtlpExporter();
            })
            .WithLogging(logging => logging.AddOtlpExporter())
            .WithMetrics(metrics =>
            {
                configureMetrics(metrics);
                metrics.AddOtlpExporter();
            })));
    }

    /// <summary>Flushes what the scenario emitted, then shuts the SDK down.</summary>
    /// <remarks>
    /// The flush is explicit rather than left to the providers' own shutdown because the runner
    /// sets an effectively infinite metric export interval: without it a scenario's metrics would
    /// never leave the process.
    /// The signals share one budget so application and provider shutdown also fit inside the
    /// driver's process timeout.
    /// </remarks>
    public void Dispose()
    {
        try
        {
            TelemetryLifecycle.FlushBeforeShutdown(
                this.sdk.TracerProvider.ForceFlush,
                this.sdk.LoggerProvider.ForceFlush,
                this.sdk.MeterProvider.ForceFlush,
                TotalFlushTimeoutMilliseconds);
        }
        finally
        {
            this.sdk.Dispose();
        }
    }
}

internal static class TelemetryLifecycle
{
    internal static void FlushBeforeShutdown(
        Func<int, bool> flushTraces,
        Func<int, bool> flushLogs,
        Func<int, bool> flushMetrics,
        int timeoutMilliseconds,
        Func<long>? elapsedMilliseconds = null)
    {
        var elapsed = Stopwatch.StartNew();
        elapsedMilliseconds ??= () => elapsed.ElapsedMilliseconds;

        var remaining = Remaining();
        var traces = Task.Run(() => flushTraces(remaining));
        var logs = Task.Run(() => flushLogs(remaining));
        Task.WhenAll(traces, logs).GetAwaiter().GetResult();

        EnsureFlushed("trace", traces.Result);
        EnsureFlushed("log", logs.Result);
        Flush("metric", flushMetrics, Remaining());

        int Remaining() =>
            Math.Max(0, timeoutMilliseconds - (int)elapsedMilliseconds());
    }

    private static void Flush(string signal, Func<int, bool> operation, int timeoutMilliseconds)
    {
        EnsureFlushed(signal, operation(timeoutMilliseconds));
    }

    private static void EnsureFlushed(string signal, bool flushed)
    {
        if (!flushed)
        {
            throw new InvalidOperationException(
                $"{signal} flush did not complete within the shutdown budget");
        }
    }
}
