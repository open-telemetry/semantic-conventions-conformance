// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Scenario;

/// <summary>How a long-running scenario learns that the runner is finished with it.</summary>
public static class ScenarioLifecycle
{
    /// <summary>
    /// Completes when standard input closes, which is how the driver says stop.
    /// </summary>
    /// <remarks>
    /// A closed pipe rather than a signal: it means the same thing on every platform, and
    /// returning is what gives an SDK the chance to flush, so a scenario that exits any other way
    /// reports less than it produced. The protocol is the same in every domain.
    /// <para>
    /// The read runs on a thread pool thread because standard input is a synchronous handle when
    /// it is a pipe on Windows: awaiting it directly would block the caller rather than the
    /// scenario's server.
    /// </para>
    /// </remarks>
    public static Task WaitForEofAsync() => Task.Run(() =>
    {
        var input = Console.OpenStandardInput();
        var discarded = new byte[1];
        while (input.Read(discarded, 0, 1) > 0)
        {
            // Nothing arrives on standard input; only its close is the signal.
        }
    });
}
