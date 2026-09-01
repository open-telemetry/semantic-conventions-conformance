// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Text.Json;
using Xunit;

namespace OpenTelemetry.Conformance.Http.Tests;

public class HttpContractTests
{
    [Fact]
    public void ItIsReadFromTheFileEveryLanguageReads() =>
        Assert.NotEmpty(HttpContract.Exchanges);

    // A field nothing else reads: without this, the contract renaming it would bind null and
    // every other test here would still pass.
    [Fact]
    public void EveryExchangeHasADescription() =>
        Assert.DoesNotContain(
            HttpContract.Exchanges,
            exchange => string.IsNullOrWhiteSpace(exchange.Description));

    [Fact]
    public void ReadinessIsNotMeasured()
    {
        Assert.Contains(HttpContract.Exchanges, exchange => exchange.Readiness);
        Assert.DoesNotContain(HttpContract.Requests, exchange => exchange.Readiness);
        Assert.Equal(HttpContract.Exchanges.Count - 1, HttpContract.Requests.Count);
    }

    [Fact]
    public void EachOrdinalSelectsOneIndependentRequest()
    {
        Assert.Equal(HttpContract.Requests, [
            .. Enumerable.Range(0, HttpContract.Requests.Count).Select(HttpContract.Request),
        ]);
        Assert.Throws<ArgumentOutOfRangeException>(() => HttpContract.Request(-1));
        Assert.Throws<ArgumentOutOfRangeException>(
            () => HttpContract.Request(HttpContract.Requests.Count));
    }

    [Fact]
    public void AScenarioIndexThatIsNotSetSaysSo()
    {
        var previous = Environment.GetEnvironmentVariable(HttpContract.ScenarioIndexVariable);
        try
        {
            Environment.SetEnvironmentVariable(HttpContract.ScenarioIndexVariable, null);

            var error = Assert.Throws<InvalidOperationException>(HttpContract.ScenarioRequest);

            Assert.Equal($"{HttpContract.ScenarioIndexVariable} is not set", error.Message);
        }
        finally
        {
            Environment.SetEnvironmentVariable(HttpContract.ScenarioIndexVariable, previous);
        }
    }

    // Parsed, not compared as text: whitespace and key order are a language's choice of JSON
    // writer, and neither is part of the contract.
    [Fact]
    public void WhitespaceAndKeyOrderAreTheJsonWritersBusiness()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));

        HttpContract.Verify(
            users,
            new HttpContract.Response(users.Status, "{ \"name\" :\"Alice\",\n  \"id\": 123 }"));
    }

    [Fact]
    public void AnAnswerThatIsNotJsonSaysSo()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));

        var failure = Assert.Throws<InvalidOperationException>(
            () => HttpContract.Verify(users, new HttpContract.Response(users.Status, "<html>")));

        Assert.Contains(
            "did not return the expected JSON", failure.Message, StringComparison.Ordinal);
        Assert.IsAssignableFrom<JsonException>(failure.InnerException);
    }

    [Fact]
    public void AnUnexpectedJsonBodyIncludesBoundedDetails()
    {
        var users = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));
        var actual = $"{{\"name\":\"Bob\",\"padding\":\"{new string('x', 500)}\"}}";

        var failure = Assert.Throws<InvalidOperationException>(
            () => HttpContract.Verify(users, new HttpContract.Response(users.Status, actual)));

        Assert.Contains("returned {\"name\":\"Bob\"", failure.Message, StringComparison.Ordinal);
        Assert.Contains("..., expected ", failure.Message, StringComparison.Ordinal);
        Assert.True(failure.Message.Length < 500);
    }

    [Fact]
    public void AQueryStringDoesNotChangeWhichExchangeAnswers()
    {
        var plain = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/123"));
        var withQuery = Assert.IsType<HttpContract.Exchange>(
            HttpContract.Find("GET", "/users/123?fields=name&verbose=true"));

        Assert.Equal(plain.Status, withQuery.Status);
        Assert.Equal(plain.ResponseBody, withQuery.ResponseBody);
    }

    [Fact]
    public void TheMethodIsPartOfTheLookup() =>
        Assert.Null(HttpContract.Find("DELETE", "/items"));

    [Fact]
    public void AnUnknownPathDescribesNoExchange() =>
        Assert.Null(HttpContract.Find("GET", "/nope"));

    [Fact]
    public void TheBodyThatArrivedIsWhatIsEchoed()
    {
        var items = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("POST", "/items"));

        Assert.Equal(
            "{\"created\": true, \"payload\": {\"name\": \"widget\"}}",
            items.RenderResponseBody("{\"name\": \"widget\"}"));
    }

    [Fact]
    public void ARequestThatCarriedNoBodyEchoesAnEmptyObject()
    {
        var items = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("POST", "/items"));

        Assert.Equal(items.RenderResponseBody(null), items.RenderResponseBody(string.Empty));
        Assert.Equal("{\"created\": true, \"payload\": {}}", items.RenderResponseBody(null));
    }
}
