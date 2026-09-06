// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Http;

/// <summary>
/// Shared support for .NET client scenarios: the request contract, sent by the library under test.
/// </summary>
/// <remarks>
/// Only a <em>client</em> scenario needs this: it is the sender, so the requests have to leave the
/// library under test. A server scenario is driven from outside its own process by
/// <c>otel-http-drive</c> and never sends anything.
/// <para>The shared telemetry contract checks what these requests emit.</para>
/// </remarks>
public static class HttpClientWorkload
{
    /// <summary>Sends one request using the HTTP client library under test.</summary>
    /// <remarks><paramref name="body"/> is null for a request that carries none.</remarks>
    public delegate Task<HttpContract.Response> Sender(string method, string url, string? body);

    /// <summary>
    /// Sends the runner-selected contract request at <paramref name="baseUrl"/> through
    /// <paramref name="send"/>.
    /// </summary>
    /// <remarks>
    /// No health check: the runner starts the mock server a client scenario calls and waits for it
    /// to answer before running the scenario at all.
    /// </remarks>
    public static async Task DriveAsync(string baseUrl, Sender send)
    {
        await DriveAsync(baseUrl, send, HttpContract.ScenarioRequest()).ConfigureAwait(false);
    }

    internal static async Task DriveAsync(
        string baseUrl,
        Sender send,
        HttpContract.Exchange exchange)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(baseUrl);
        ArgumentNullException.ThrowIfNull(send);

        var normalizedBaseUrl = baseUrl.TrimEnd('/');
        var response = await send(
                exchange.Method, normalizedBaseUrl + exchange.Path, exchange.Body)
            .ConfigureAwait(false);
        Console.WriteLine(
            $"{exchange.Method} {exchange.Path} -> {response.StatusCode} {Abbreviate(response.Body)}");
    }

    private static string Abbreviate(string value)
    {
        var singleLine = value.ReplaceLineEndings(" ");
        return singleLine.Length <= 60 ? singleLine : singleLine[..60];
    }
}
