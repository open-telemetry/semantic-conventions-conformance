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
                "GET /users/456?fields=name&verbose=true",
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
        await HttpClientWorkload.DriveAsync($"{BaseUrl}/", (method, url, body) =>
        {
            firstUrl ??= url;
            var path = $"/{new Uri(url).PathAndQuery.TrimStart('/')}";
            return Task.FromResult(HttpServerWorkload.Respond(method, path, body));
        });

        Assert.Equal($"{BaseUrl}/users/123", firstUrl);
    }

    [Fact]
    public void AWrongStatusFailsTheRun()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));

        var failure = Assert.Throws<ContractException>(() => HttpClientWorkload.Verify(
            users, new HttpContract.Response(500, users.ResponseBody)));
        Assert.Contains("answered 500", failure.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void WhitespaceAndKeyOrderAreTheJsonWritersBusiness()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));

        HttpClientWorkload.Verify(
            users,
            new HttpContract.Response(users.Status, "{ \"name\" :\"Alice\",\n  \"id\": 123 }"));
    }

    [Fact]
    public void AnAnswerThatIsNotJsonSaysSo()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));

        var failure = Assert.Throws<ContractException>(() => HttpClientWorkload.Verify(
            users, new HttpContract.Response(users.Status, "<html>")));

        Assert.StartsWith("not JSON", failure.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ABlankBaseUrlIsRefusedBeforeAnythingIsSent() =>
        await Assert.ThrowsAsync<ArgumentException>(() => HttpClientWorkload.DriveAsync(
            "  ", (method, url, body) => Task.FromResult(new HttpContract.Response(200, "{}"))));

    /// <summary>A sender backed by the other side of the same contract, which is what a run
    /// measures.</summary>
    private static async Task<List<string>> DriveAgainstTheContractAsync()
    {
        List<string> sent = [];
        await HttpClientWorkload.DriveAsync(BaseUrl, (method, url, body) =>
        {
            var path = url[BaseUrl.Length..];
            sent.Add($"{method} {path}");
            return Task.FromResult(HttpServerWorkload.Respond(method, path, body));
        });
        return sent;
    }
}
