// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Text.Json.Nodes;

namespace OpenTelemetry.Conformance.Http;

/// <summary>
/// Shared support for .NET client scenarios: the request contract, sent by the library under test.
/// </summary>
/// <remarks>
/// Only a <em>client</em> scenario needs this: it is the sender, so the requests have to leave the
/// library under test. A server scenario is driven from outside its own process by
/// <c>otel-http-drive</c> and never sends anything.
/// <para>
/// Every answer is checked against its exchange, so a server answering different traffic from the
/// rest fails the run rather than quietly producing a coverage file that cannot be compared with
/// the others.
/// </para>
/// </remarks>
public static class HttpClientWorkload
{
    /// <summary>Sends one request using the HTTP client library under test.</summary>
    /// <remarks><paramref name="body"/> is null for a request that carries none.</remarks>
    public delegate Task<HttpContract.Response> Sender(string method, string url, string? body);

    /// <summary>
    /// Sends <see cref="HttpContract.Requests"/> at <paramref name="baseUrl"/> through
    /// <paramref name="send"/>.
    /// </summary>
    /// <remarks>
    /// No health check: the runner starts the mock server a client scenario calls and waits for it
    /// to answer before running the scenario at all.
    /// </remarks>
    public static async Task DriveAsync(string baseUrl, Sender send)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(baseUrl);
        ArgumentNullException.ThrowIfNull(send);

        foreach (var exchange in HttpContract.Requests)
        {
            var response = await send(exchange.Method, baseUrl + exchange.Path, exchange.Body)
                .ConfigureAwait(false);
            Console.WriteLine(
                $"{exchange.Method} {exchange.Path} -> {response.StatusCode} {Abbreviate(response.Body)}");
            Verify(exchange, response);
        }
    }

    /// <summary>Checks one answer against the exchange that describes it.</summary>
    public static void Verify(HttpContract.Exchange exchange, HttpContract.Response response)
    {
        ArgumentNullException.ThrowIfNull(exchange);
        ArgumentNullException.ThrowIfNull(response);

        if (response.StatusCode != exchange.Status)
        {
            throw new ContractException(
                $"{exchange.Method} {exchange.Path} answered {response.StatusCode}, but the "
                + $"contract's request answers {exchange.Status}");
        }

        // Parsed, not compared as text: whitespace and key order are a language's choice of JSON
        // writer, and neither is part of the contract.
        var expectedBody = HttpContract.Parse(exchange.RenderResponseBody(exchange.Body));
        var actualBody = HttpContract.Parse(response.Body);
        if (!JsonNode.DeepEquals(expectedBody, actualBody))
        {
            throw new ContractException(
                $"{exchange.Method} {exchange.Path} answered {actualBody.ToJsonString()}, but the "
                + $"contract's request answers {expectedBody.ToJsonString()}");
        }
    }

    private static string Abbreviate(string value)
    {
        var singleLine = value.Replace('\r', ' ').Replace('\n', ' ');
        return singleLine.Length <= 60 ? singleLine : singleLine[..60];
    }
}
