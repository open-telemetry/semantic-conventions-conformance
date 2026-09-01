// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

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
    public void AQueryStringDoesNotChangeWhichExchangeAnswers()
    {
        var plain = Assert.IsType<HttpContract.Exchange>(HttpContract.Find("GET", "/users/456"));
        var withQuery = Assert.IsType<HttpContract.Exchange>(
            HttpContract.Find("GET", "/users/456?fields=name&verbose=true"));

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
