// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Reflection;
using System.Globalization;
using System.Text.Json.Nodes;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace OpenTelemetry.Conformance.Http;

/// <summary>The HTTP conformance exchanges, as .NET reads them.</summary>
/// <remarks>
/// Read from the <c>otel-http-contract.yaml</c> manifest resource, which the build embeds from
/// <c>tools/http/test-client/contract.yaml</c> — the one place it is written down, so a .NET
/// scenario and a scenario in any other language are measured against the same traffic.
/// <para>
/// <see cref="Exchanges"/> carries the concrete traffic and its answers. Every .NET framework
/// shares this class rather than restating them, while server scenarios declare routes in their
/// framework's native form.
/// </para>
/// </remarks>
public static class HttpContract
{
    /// <summary>Every route answers JSON, so a scenario has one content type rather than a rule
    /// per route.</summary>
    public const string ContentType = "application/json";

    /// <summary>
    /// Fixed rather than the HTTP library's default, so a server scenario sees the same client
    /// whichever language sent the requests.
    /// </summary>
    public const string UserAgent = "otel-http-conformance/1";

    public const string ScenarioIndexVariable = "OTEL_CONFORMANCE_SCENARIO_INDEX";

    private const string ResourceName = "otel-http-contract.yaml";

    private static readonly Lazy<IReadOnlyList<Exchange>> Contract = new(Load);

    private static readonly Exchange Readiness =
        new(
            "GET",
            "/health",
            null,
            200,
            "{\"ok\": true}",
            true,
            "Checks whether the server is ready.");

    /// <summary>Every exchange the contract describes, including readiness, in order.</summary>
    public static IReadOnlyList<Exchange> Exchanges => [Readiness, .. Contract.Value];

    /// <summary>The measured requests to send, in order.</summary>
    public static IReadOnlyList<Exchange> Requests => Contract.Value;

    /// <summary>One concrete request and the answer the contract requires.</summary>
    /// <remarks>
    /// <see cref="Body"/> is null for a request that carries none. The only substitution in
    /// <see cref="ResponseBody"/> is the literal <c>${requestBody}</c>, for the body that arrived.
    /// </remarks>
    public sealed record Exchange(
        string Method,
        string Path,
        string? Body,
        int Status,
        string ResponseBody,
        bool Readiness,
        string Description)
    {
        /// <summary>The response body with the request body inserted.</summary>
        public string RenderResponseBody(string? requestBody) => this.ResponseBody.Replace(
            "${requestBody}",
            string.IsNullOrEmpty(requestBody) ? "{}" : requestBody,
            StringComparison.Ordinal);
    }

    /// <summary>A status and a body: what a request came back as, and what a route answers.</summary>
    /// <remarks>
    /// One type for both directions, because they are the same pair — which is why the other
    /// languages carry it as a plain tuple.
    /// </remarks>
    public sealed record Response(int StatusCode, string Body);

    /// <summary>The one request selected by the runner's zero-based contract index.</summary>
    public static Exchange ScenarioRequest()
    {
        var raw = Environment.GetEnvironmentVariable(ScenarioIndexVariable);
        if (!int.TryParse(
                raw,
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out var index)
            || index < 0
            || raw != index.ToString(CultureInfo.InvariantCulture))
        {
            throw new InvalidOperationException(
                $"{ScenarioIndexVariable} must be a zero-based decimal index, got '{raw}'");
        }

        return Request(index);
    }

    internal static Exchange Request(int index)
    {
        if (index < 0 || index >= Requests.Count)
        {
            throw new ArgumentOutOfRangeException(
                nameof(index),
                $"{ScenarioIndexVariable}={index} selects no contract entry; "
                + $"expected 0..{Requests.Count - 1}");
        }

        return Requests[index];
    }

    internal static void Verify(Exchange exchange, Response response)
    {
        if (response.StatusCode != exchange.Status)
        {
            throw new InvalidOperationException(
                $"{exchange.Method} {exchange.Path} answered {response.StatusCode}, "
                + $"expected {exchange.Status}");
        }

        JsonNode? actual;
        JsonNode? expected;
        try
        {
            actual = JsonNode.Parse(response.Body);
            expected = JsonNode.Parse(exchange.RenderResponseBody(exchange.Body));
        }
        catch (System.Text.Json.JsonException error)
        {
            throw new InvalidOperationException(
                $"{exchange.Method} {exchange.Path} did not return the expected JSON",
                error);
        }

        if (!JsonNode.DeepEquals(actual, expected))
        {
            throw new InvalidOperationException(
                $"{exchange.Method} {exchange.Path} returned an unexpected JSON body");
        }
    }

    /// <summary>The exchange answering <c>method path</c>, if the contract describes one.</summary>
    internal static Exchange? Find(string method, string path)
    {
        var withoutQuery = WithoutQuery(path);
        return Exchanges.FirstOrDefault(exchange =>
            exchange.Method == method && WithoutQuery(exchange.Path) == withoutQuery);
    }

    private static string WithoutQuery(string path)
    {
        var query = path.IndexOf('?', StringComparison.Ordinal);
        return query == -1 ? path : path[..query];
    }

    private static IReadOnlyList<Exchange> Load()
    {
        var assembly = typeof(HttpContract).GetTypeInfo().Assembly;
        using var stream = assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException(
                $"{ResourceName} is not embedded in {assembly.GetName().Name} — the build embeds "
                + "it from tools/http/test-client/contract.yaml");
        using var reader = new StreamReader(stream);
        var document = new DeserializerBuilder()
            .WithNamingConvention(CamelCaseNamingConvention.Instance)
            .IgnoreUnmatchedProperties()
            .Build()
            .Deserialize<ContractDocument>(reader);
        var scenarios = document?.Scenarios;
        if (scenarios is null || scenarios.Count == 0)
        {
            throw new InvalidOperationException($"{ResourceName} is empty");
        }

        return scenarios.Select(scenario => new Exchange(
            scenario.Action.Request.Method,
            scenario.Action.Request.Path,
            scenario.Action.Request.Body,
            scenario.Action.Response.Status,
            scenario.Action.Response.Body,
            false,
            scenario.Description)).ToArray();
    }

    private sealed class ContractDocument
    {
        public string Description { get; init; } = string.Empty;

        public List<ScenarioEntry> Scenarios { get; init; } = [];
    }

    private sealed class ScenarioEntry
    {
        public string Description { get; init; } = string.Empty;

        public ContractAction Action { get; init; } = new();
    }

    private sealed class ContractAction
    {
        public ContractRequest Request { get; init; } = new();

        public ContractResponse Response { get; init; } = new();
    }

    private sealed class ContractRequest
    {
        public string Method { get; init; } = string.Empty;

        public string Path { get; init; } = string.Empty;

        public string? Body { get; init; }
    }

    private sealed class ContractResponse
    {
        public int Status { get; init; }

        public string Body { get; init; } = string.Empty;
    }
}
