// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Xunit;

namespace OpenTelemetry.Conformance.Http.Tests;

public class HttpClientWorkloadTests
{
    private const string BaseUrl = "http://127.0.0.1:0";

    [Fact]
    public async Task BothSidesOfTheContractAgree()
    {
        Assert.Equal(
            [
                "GET /users/123",
                "GET /users/123?fields=name&verbose=true",
                "POST /items",
                "GET /status/404",
                "GET /status/500",
            ],
            await DriveAgainstTheContractAsync());
    }

    [Fact]
    public async Task ATrailingSlashDoesNotCreateADoubleSlash()
    {
        string? firstUrl = null;
        await HttpClientWorkload.DriveAsync(
            $"{BaseUrl}/",
            (method, url, body) =>
            {
                firstUrl ??= url;
                var path = $"/{new Uri(url).PathAndQuery.TrimStart('/')}";
                return Task.FromResult(HttpServerWorkload.Respond(method, path, body));
            },
            HttpContract.Request(0));

        Assert.Equal($"{BaseUrl}/users/123", firstUrl);
    }

    [Fact]
    public async Task AWrongResponseFailsTheScenario()
    {
        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            HttpClientWorkload.DriveAsync(
                BaseUrl,
                (method, url, body) =>
                    Task.FromResult(new HttpContract.Response(599, "not JSON")),
                HttpContract.Request(0)));
    }

    [Fact]
    public async Task ABlankBaseUrlIsRefusedBeforeAnythingIsSent() =>
        await Assert.ThrowsAsync<ArgumentException>(() => HttpClientWorkload.DriveAsync(
            "  ",
            (method, url, body) => Task.FromResult(new HttpContract.Response(200, "{}")),
            HttpContract.Request(0)));

    /// <summary>A sender backed by the other side of the same contract, which is what a run
    /// measures.</summary>
    private static async Task<List<string>> DriveAgainstTheContractAsync()
    {
        List<string> sent = [];
        for (var index = 0; index < HttpContract.Requests.Count; index++)
        {
            await HttpClientWorkload.DriveAsync(
                BaseUrl,
                (method, url, body) =>
                {
                    var path = url[BaseUrl.Length..];
                    sent.Add($"{method} {path}");
                    return Task.FromResult(HttpServerWorkload.Respond(method, path, body));
                },
                HttpContract.Request(index));
        }

        return sent;
    }
}
