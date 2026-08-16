// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Scenario;

/// <summary>What the runner told a scenario, in the one place a scenario reads it.</summary>
public static class ScenarioEnvironment
{
    /// <summary>The value of <paramref name="name"/>, or a failure naming what was missing.</summary>
    public static string Require(string name)
    {
        var value = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException(
                $"required environment variable is missing: {name}");
        }

        return value;
    }
}
