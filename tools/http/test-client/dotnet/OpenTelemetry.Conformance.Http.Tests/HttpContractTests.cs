// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Xunit;

namespace OpenTelemetry.Conformance.Http.Tests;

public class HttpContractTests
{
    [Fact]
    public void CompleteActionTableIncludesReadinessAndMeasuredRequests()
    {
        var exchanges = HttpContract.DeserializeActions(TestActions.Json);

        Assert.True(exchanges[0].Readiness);
        Assert.DoesNotContain(exchanges.Skip(1), exchange => exchange.Readiness);
        Assert.Equal(6, exchanges.Count);
    }

    [Fact]
    public void RepeatedLookupsReuseOneParsedTable()
    {
        // A server scenario answers every request from this table, so parsing it per
        // request would charge the measured process on the path its instrumentation
        // is timing.
        var first = HttpContract.CachedActions(TestActions.Json);
        var second = HttpContract.CachedActions(TestActions.Json);

        Assert.Same(first, second);
        Assert.Same(first[0], second[0]);
        Assert.NotSame(first, HttpContract.DeserializeActions(TestActions.Json));
    }

    [Fact]
    public void SingularClientActionIsDecoded()
    {
        var exchange = HttpContract.DeserializeAction(
            """{"request":{"method":"POST","path":"/items","body":"{}"},"response":{"status":201,"body":"{}"}}""");

        Assert.Equal("POST", exchange.Method);
        Assert.Equal("/items", exchange.Path);
        Assert.Equal("{}", exchange.Body);
        Assert.Equal(201, exchange.Status);
    }

    [Fact]
    public void MissingSelectedActionNamesTheVariable()
    {
        var previous = Environment.GetEnvironmentVariable(HttpContract.ActionVariable);
        try
        {
            Environment.SetEnvironmentVariable(HttpContract.ActionVariable, null);
            var error = Assert.Throws<InvalidOperationException>(HttpContract.ScenarioRequest);
            Assert.Equal($"{HttpContract.ActionVariable} is not set", error.Message);
        }
        finally
        {
            Environment.SetEnvironmentVariable(HttpContract.ActionVariable, previous);
        }
    }

    [Fact]
    public void MalformedJsonAndUnknownFieldsAreRejected()
    {
        Assert.Contains(
            "malformed JSON",
            Assert.Throws<InvalidOperationException>(
                () => HttpContract.DeserializeAction("{")).Message);
        Assert.Contains(
            "unknown field",
            Assert.Throws<InvalidOperationException>(
                () => HttpContract.DeserializeAction(
                    """{"request":{},"response":{},"extra":true}""")).Message);
    }

    [Fact]
    public void MalformedAndEmptyActionTablesAreRejected()
    {
        Assert.Throws<InvalidOperationException>(
            () => HttpContract.DeserializeActions("{"));
        Assert.Throws<InvalidOperationException>(
            () => HttpContract.DeserializeActions("[]"));
    }

    [Fact]
    public void RequestAndResponseLookupPreservesMethodQueryAndBodyHandling()
    {
        var plain = Assert.IsType<HttpContract.Exchange>(
            HttpContract.Find(TestActions.Exchanges, "GET", "/users/123"));
        var withQuery = Assert.IsType<HttpContract.Exchange>(
            HttpContract.Find(
                TestActions.Exchanges,
                "GET",
                "/users/123?fields=name&verbose=true"));
        var items = Assert.IsType<HttpContract.Exchange>(
            HttpContract.Find(TestActions.Exchanges, "POST", "/items"));

        Assert.Equal(plain.Status, withQuery.Status);
        Assert.Null(HttpContract.Find(TestActions.Exchanges, "DELETE", "/items"));
        Assert.Equal(
            "{\"created\": true, \"payload\": {\"name\": \"widget\"}}",
            items.RenderResponseBody("{\"name\": \"widget\"}"));
    }
}
