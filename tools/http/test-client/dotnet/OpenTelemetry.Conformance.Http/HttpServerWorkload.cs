// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Globalization;

namespace OpenTelemetry.Conformance.Http;

/// <summary>Shared support for .NET server scenarios.</summary>
/// <remarks>
/// A server scenario declares routes with the framework under test — that declaration is what an
/// instrumentation reads <c>http.route</c> from — and then asks this class what to answer. Every
/// .NET framework therefore agrees on the statuses and bodies without forcing its route
/// construction into a shared runtime model.
/// <para>
/// The requests are sent by <c>otel-http-drive</c> from another process, which checks each answer
/// against the same contract.
/// </para>
/// </remarks>
public static class HttpServerWorkload
{
    /// <summary>
    /// The port a server scenario listens on. <c>otel-http-drive</c> chooses it, which is what
    /// lets different scenarios run in parallel without colliding.
    /// </summary>
    public const string PortVariable = "OTEL_HTTP_SCENARIO_PORT";

    /// <summary>What the contract answers to one request.</summary>
    /// <remarks>
    /// The whole answer contract in one method, so every .NET framework answers identically.
    /// <paramref name="requestBody"/> is null for a request that carried none.
    /// </remarks>
    public static HttpContract.Response Respond(string method, string path, string? requestBody)
    {
        var exchange = HttpContract.Find(method, path);
        return exchange is null
            ? new HttpContract.Response(404, "{\"message\": \"no such route\"}")
            : new HttpContract.Response(
                exchange.Status, exchange.RenderResponseBody(requestBody));
    }

    /// <summary>The port the driver told this scenario to listen on.</summary>
    public static int ScenarioPort()
    {
        var value = Environment.GetEnvironmentVariable(PortVariable);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException(
                $"{PortVariable} is not set — a server scenario is started by `otel-http-drive`, "
                + "which chooses the port");
        }

        return int.Parse(value, CultureInfo.InvariantCulture);
    }
}
