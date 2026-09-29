// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Scenario;

using Xunit;

public sealed class TelemetryLifecycleTests
{
    [Fact]
    public void FlushesTracesAndLogsBeforeMetrics()
    {
        var events = new List<string>();

        TelemetryLifecycle.FlushBeforeShutdown(
            Record("trace"),
            Record("log"),
            Record("metric"),
            15_000,
            () => 0);

        Assert.Equal("metric", events[^1]);
        Assert.Equal(["log", "trace"], events[..2].Order());

        Func<int, bool> Record(string signal) => timeout =>
        {
            lock (events)
            {
                events.Add(signal);
            }

            return true;
        };
    }

    [Fact]
    public void AwaitsEachFlushAndPassesTheRemainingBudget()
    {
        var timeouts = new List<int>();
        var elapsed = new Queue<long>([100, 400, 900]);

        TelemetryLifecycle.FlushBeforeShutdown(
            Record,
            Record,
            Record,
            1_000,
            () => elapsed.Dequeue());

        Assert.Equal([900, 900, 600], timeouts);

        bool Record(int timeout)
        {
            lock (timeouts)
            {
                timeouts.Add(timeout);
            }

            return true;
        }
    }

    [Fact]
    public void PropagatesAFlushFailureAndDoesNotFlushMetricsEarly()
    {
        var logFlushed = false;
        var metricFlushed = false;

        var error = Assert.Throws<InvalidOperationException>(() =>
            TelemetryLifecycle.FlushBeforeShutdown(
                timeout => false,
                timeout => logFlushed = true,
                timeout => metricFlushed = true,
                15_000,
                () => 0));

        Assert.Contains("trace flush", error.Message);
        Assert.True(logFlushed);
        Assert.False(metricFlushed);
    }

    [Fact]
    public void GivesAFlushNoTimeAfterTheBoundedBudgetExpires()
    {
        var timeouts = new List<int>();

        TelemetryLifecycle.FlushBeforeShutdown(
            Record,
            Record,
            Record,
            10,
            () => 11);

        Assert.Equal([0, 0, 0], timeouts);

        bool Record(int timeout)
        {
            lock (timeouts)
            {
                timeouts.Add(timeout);
            }

            return true;
        }
    }
}
