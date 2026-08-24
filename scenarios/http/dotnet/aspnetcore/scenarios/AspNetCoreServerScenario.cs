// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using OpenTelemetry.Conformance.Scenario;

namespace OpenTelemetry.Conformance.Http.AspNetCore;

/// <summary>Hosts the shared HTTP exchanges in ASP.NET Core until the driver says stop.</summary>
/// <remarks>
/// The routes are declared as minimal APIs because an instrumentation reads <c>http.route</c> from
/// ASP.NET Core's own endpoint metadata: <c>MapGet("/users/{userId}", ...)</c> is the route
/// template, and the concrete <c>/users/123</c> that arrives never appears in it. Answering is an
/// exact lookup of the concrete request and is therefore identical for every framework.
/// <para>
/// The requests are sent by <c>otel-http-drive</c> from another process, so nothing this process
/// loads can instrument the sender and record client spans in a server scenario's report. It
/// listens on the port the driver chose and shuts down when the driver closes its standard input,
/// which is what gives the SDK a chance to flush.
/// </para>
/// </remarks>
public static class AspNetCoreServerScenario
{
    /// <summary>Hosts them plainly, for a scenario whose instrumentation attaches itself.</summary>
    /// <remarks>
    /// .NET instrumentations subscribe to the runtime's diagnostic sources through the SDK rather
    /// than wrapping each server, so unlike frameworks that are instrumented by decoration this
    /// workload has nothing to hand its launcher.
    /// </remarks>
    public static async Task RunAsync()
    {
        var builder = WebApplication.CreateBuilder();

        // 127.0.0.1 rather than localhost: a scenario should never be reachable from off the
        // machine, and the driver connects to the loopback address it chose the port on.
        builder.WebHost.UseUrls(
            $"http://127.0.0.1:{HttpServerWorkload.ScenarioPort()}");

        var app = builder.Build();
        app.MapGet("/health", AnswerAsync);
        app.MapGet("/users/{userId}", AnswerAsync);
        app.MapPost("/items", AnswerAsync);
        app.MapGet("/status/{code}", AnswerAsync);

        // StartAsync rather than RunAsync: the latter owns the shutdown signal, and this scenario's
        // signal is the driver closing standard input.
        await app.StartAsync().ConfigureAwait(false);
        try
        {
            await ScenarioLifecycle.WaitForEofAsync().ConfigureAwait(false);
        }
        finally
        {
            await app.StopAsync().ConfigureAwait(false);
        }
    }

    private static async Task AnswerAsync(HttpContext context)
    {
        using var reader = new StreamReader(context.Request.Body);
        var requestBody = await reader.ReadToEndAsync().ConfigureAwait(false);

        // Request.Path excludes the query string, which the contract's answers do not depend on.
        var answer = HttpServerWorkload.Respond(
            context.Request.Method, context.Request.Path, requestBody);

        context.Response.StatusCode = answer.StatusCode;
        context.Response.ContentType = HttpContract.ContentType;
        await context.Response.WriteAsync(answer.Body).ConfigureAwait(false);
    }
}
