// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Net.Http.Headers;
using System.Text;
using OpenTelemetry.Conformance.Scenario;

namespace OpenTelemetry.Conformance.Http.SystemNetHttp;

/// <summary>Runs the shared request contract through a <c>System.Net.Http.HttpClient</c>.</summary>
/// <remarks>
/// The mock server answering the requests is declared by the scenario package and started by the
/// runner, so a client scenario is measured against the same traffic as every other one without
/// hosting a server of its own.
/// </remarks>
public static class HttpClientScenario
{
    /// <summary>
    /// Runs it through a plain client, for a scenario whose instrumentation attaches itself.
    /// </summary>
    /// <remarks>
    /// .NET instrumentations subscribe to <c>System.Net.Http</c>'s diagnostic sources through the
    /// SDK rather than wrapping each client, so unlike libraries that are instrumented by
    /// decoration this workload has nothing to hand its launcher.
    /// </remarks>
    public static async Task RunAsync()
    {
        var baseUrl = ScenarioEnvironment.Require("MOCK_SERVER_URL");

        // One client for the whole sequence, which is how HttpClient is meant to be used and what
        // an instrumentation is written against.
        using var client = new HttpClient();

        await HttpClientWorkload.DriveAsync(
            baseUrl,
            async (method, url, body) =>
            {
                using var request = new HttpRequestMessage(new HttpMethod(method), url);
                request.Headers.UserAgent.ParseAdd(HttpContract.UserAgent);
                if (body is not null)
                {
                    request.Content = new StringContent(
                        body, Encoding.UTF8, new MediaTypeHeaderValue(HttpContract.ContentType));
                }

                using var response = await client.SendAsync(request).ConfigureAwait(false);
                return new HttpContract.Response(
                    (int)response.StatusCode,
                    await response.Content.ReadAsStringAsync().ConfigureAwait(false));
            }).ConfigureAwait(false);
    }
}
