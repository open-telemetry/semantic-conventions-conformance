// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Xunit;

namespace OpenTelemetry.Conformance.Http.Tests;

public class HttpServerWorkloadTests
{
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

    [Fact]
    public void TrafficTheContractDoesNotDescribeIsRefused()
    {
        var answer = HttpServerWorkload.Respond("GET", "/nope", null);

        Assert.Equal(404, answer.StatusCode);
    }
}
