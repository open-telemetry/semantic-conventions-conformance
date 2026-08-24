// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Xunit;

namespace OpenTelemetry.Conformance.Http.Tests;

public class HttpServerWorkloadTests
{
    [Fact]
    public void TheScenarioPortComesFromTheDriver()
    {
        var previous = Environment.GetEnvironmentVariable(HttpServerWorkload.PortVariable);
        try
        {
            Environment.SetEnvironmentVariable(HttpServerWorkload.PortVariable, "4317");

            Assert.Equal(4317, HttpServerWorkload.ScenarioPort());
        }
        finally
        {
            Environment.SetEnvironmentVariable(HttpServerWorkload.PortVariable, previous);
        }
    }

    [Theory]
    [InlineData("not-a-port")]
    [InlineData("0")]
    [InlineData("65536")]
    public void AnInvalidScenarioPortNamesTheVariableAndValue(string value)
    {
        var previous = Environment.GetEnvironmentVariable(HttpServerWorkload.PortVariable);
        try
        {
            Environment.SetEnvironmentVariable(HttpServerWorkload.PortVariable, value);

            var error = Assert.Throws<InvalidOperationException>(
                () => HttpServerWorkload.ScenarioPort());

            Assert.Equal(
                $"{HttpServerWorkload.PortVariable} value '{value}' must be an integer from 1 through 65535",
                error.Message);
        }
        finally
        {
            Environment.SetEnvironmentVariable(HttpServerWorkload.PortVariable, previous);
        }
    }

    [Fact]
    public void AnAnswerComesFromTheContract()
    {
        var answer = HttpServerWorkload.Respond("GET", "/status/500", null);

        Assert.Equal(500, answer.StatusCode);
        Assert.Equal("{\"message\": \"status 500\"}", answer.Body);
    }

    [Fact]
    public void TheRouteIsFoundThroughTheConcretePathTheFrameworkReports()
    {
        var answer = HttpServerWorkload.Respond("GET", "/users/123?fields=name", null);

        Assert.Equal(200, answer.StatusCode);
    }

    [Fact]
    public void AScenarioThatNeverReadTheBodyWouldNotEchoIt()
    {
        var answer = HttpServerWorkload.Respond("POST", "/items", "{\"name\": \"widget\"}");

        Assert.Equal(201, answer.StatusCode);
        Assert.Equal("{\"created\": true, \"payload\": {\"name\": \"widget\"}}", answer.Body);
    }

    // A framework reporting an absent body as "" rather than null must not answer differently:
    // the ASP.NET Core scenario reads a body stream, so it always reports the empty string, and
    // every test above it passes null.
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    public void AnAbsentBodyIsTheSameWhicheverWayAFrameworkSpellsIt(string? requestBody)
    {
        var answer = HttpServerWorkload.Respond("POST", "/items", requestBody);

        Assert.Equal(201, answer.StatusCode);
        Assert.Equal("{\"created\": true, \"payload\": {}}", answer.Body);
    }

    [Fact]
    public void TrafficTheContractDoesNotDescribeIsRefused()
    {
        var answer = HttpServerWorkload.Respond("GET", "/nope", null);

        Assert.Equal(404, answer.StatusCode);
    }
}
