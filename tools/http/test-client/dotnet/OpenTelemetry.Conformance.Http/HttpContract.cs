// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace OpenTelemetry.Conformance.Http;

/// <summary>The HTTP conformance exchanges, as .NET reads them.</summary>
/// <remarks>
/// Read from the <c>otel-http-contract.json</c> manifest resource, which the build embeds from
/// <c>tools/http/test-client/contract.json</c> — the one place it is written down, so a .NET
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

    private const string ResourceName = "otel-http-contract.json";

    private static readonly JsonSerializerOptions ReadOptions =
        new() { PropertyNameCaseInsensitive = true };

    // Loaded on first use rather than in a static constructor, so a packaging problem arrives as
    // the message below rather than wrapped in TypeInitializationException.
    private static readonly Lazy<Document> Contract = new(Load);

    private static readonly Lazy<IReadOnlyList<Exchange>> MeasuredRequests =
        new(() => Contract.Value.Requests.Where(exchange => !exchange.Readiness).ToArray());

    /// <summary>Every exchange the contract describes, including readiness, in order.</summary>
    public static IReadOnlyList<Exchange> Exchanges => Contract.Value.Requests;

    /// <summary>The measured requests to send, in order.</summary>
    public static IReadOnlyList<Exchange> Requests => MeasuredRequests.Value;

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

    /// <summary>The exchange answering <c>method path</c>, if the contract describes one.</summary>
    internal static Exchange? Find(string method, string path)
    {
        var withoutQuery = WithoutQuery(path);
        return Exchanges.FirstOrDefault(exchange =>
            exchange.Method == method && WithoutQuery(exchange.Path) == withoutQuery);
    }

    /// <summary>Parses <paramref name="json"/>, so two bodies compare by structure rather than by
    /// spacing.</summary>
    /// <remarks>
    /// Internal: <c>System.Text.Json</c> is how this project reads the contract, not something a
    /// scenario has to reach for.
    /// </remarks>
    internal static JsonNode Parse(string json)
    {
        JsonNode? parsed;
        try
        {
            parsed = JsonNode.Parse(json);
        }
        catch (JsonException error)
        {
            throw new ContractException($"not JSON: {json}", error);
        }

        // An empty body parses to null rather than failing, which would otherwise surface as a
        // confusing comparison instead of "this is not JSON".
        return parsed ?? throw new ContractException($"not JSON: {json}");
    }

    private static string WithoutQuery(string path)
    {
        var query = path.IndexOf('?', StringComparison.Ordinal);
        return query == -1 ? path : path[..query];
    }

    private static Document Load()
    {
        var assembly = typeof(HttpContract).GetTypeInfo().Assembly;
        using var stream = assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException(
                $"{ResourceName} is not embedded in {assembly.GetName().Name} — the build embeds "
                + "it from tools/http/test-client/contract.json");
        return JsonSerializer.Deserialize<Document>(stream, ReadOptions)
            ?? throw new InvalidOperationException($"{ResourceName} is empty");
    }

    private sealed record Document(IReadOnlyList<Exchange> Requests);
}
