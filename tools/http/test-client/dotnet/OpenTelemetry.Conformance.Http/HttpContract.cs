// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Text.Json;

namespace OpenTelemetry.Conformance.Http;

/// <summary>The HTTP conformance exchanges supplied by the runner as JSON.</summary>
public static class HttpContract
{
    private static readonly IReadOnlySet<string> ActionFields =
        new HashSet<string> { "request", "response" };

    private static readonly IReadOnlySet<string> RequestFields =
        new HashSet<string> { "method", "path", "body" };

    private static readonly IReadOnlySet<string> ResponseFields =
        new HashSet<string> { "status", "body" };

    /// <summary>Every route answers JSON.</summary>
    public const string ContentType = "application/json";

    /// <summary>The fixed user agent shared by each client helper.</summary>
    public const string UserAgent = "otel-http-conformance/1";

    public const string ActionVariable = "OTEL_CONFORMANCE_SCENARIO_ACTION";

    public const string ActionsVariable = "OTEL_CONFORMANCE_SCENARIO_ACTIONS";

    /// <summary>Every exchange supplied by the runner, including readiness, in order.</summary>
    public static IReadOnlyList<Exchange> Exchanges =>
        DeserializeActions(RequiredEnvironment(ActionsVariable));

    /// <summary>The measured requests supplied by the runner.</summary>
    public static IReadOnlyList<Exchange> Requests => Exchanges.Skip(1).ToArray();

    /// <summary>One concrete request and the answer the contract requires.</summary>
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

    /// <summary>A status and body returned by a sender or server route.</summary>
    public sealed record Response(int StatusCode, string Body);

    /// <summary>The one request selected by the runner.</summary>
    public static Exchange ScenarioRequest() =>
        DeserializeAction(RequiredEnvironment(ActionVariable));

    internal static Exchange DeserializeAction(string json)
    {
        using var document = Parse(json, ActionVariable);
        return ToExchange(document.RootElement, $"{ActionVariable} action", readiness: false);
    }

    internal static IReadOnlyList<Exchange> DeserializeActions(string json)
    {
        using var document = Parse(json, ActionsVariable);
        if (document.RootElement.ValueKind != JsonValueKind.Array
            || document.RootElement.GetArrayLength() == 0)
        {
            throw new InvalidOperationException(
                $"{ActionsVariable} must be a non-empty JSON array of actions");
        }

        var exchanges = new List<Exchange>();
        var index = 0;
        foreach (var action in document.RootElement.EnumerateArray())
        {
            exchanges.Add(ToExchange(
                action,
                $"{ActionsVariable}[{index}] action",
                readiness: index == 0));
            index++;
        }

        return exchanges;
    }

    internal static Exchange Request(int index)
    {
        var requests = Requests;
        if (index < 0 || index >= requests.Count)
        {
            throw new ArgumentOutOfRangeException(
                nameof(index),
                $"action index {index} selects no runner action; expected 0..{requests.Count - 1}");
        }

        return requests[index];
    }

    /// <summary>The exchange answering <c>method path</c>, if the runner supplied one.</summary>
    internal static Exchange? Find(string method, string path)
        => Find(Exchanges, method, path);

    internal static Exchange? Find(
        IReadOnlyList<Exchange> exchanges,
        string method,
        string path)
    {
        var withoutQuery = WithoutQuery(path);
        return exchanges.FirstOrDefault(exchange =>
            exchange.Method == method && WithoutQuery(exchange.Path) == withoutQuery);
    }

    private static JsonDocument Parse(string json, string variable)
    {
        try
        {
            return JsonDocument.Parse(json, new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
            });
        }
        catch (JsonException error)
        {
            throw new InvalidOperationException(
                $"{variable} contains malformed JSON: {error.Message}",
                error);
        }
    }

    private static Exchange ToExchange(
        JsonElement action,
        string where,
        bool readiness)
    {
        RequireObject(action, where);
        CheckKeys(action, ActionFields, where);
        if (!action.TryGetProperty("request", out var request)
            || !action.TryGetProperty("response", out var response))
        {
            throw new InvalidOperationException(
                $"{where} requires request and response objects");
        }

        RequireObject(request, $"{where}.request");
        RequireObject(response, $"{where}.response");
        CheckKeys(request, RequestFields, $"{where}.request");
        CheckKeys(response, ResponseFields, $"{where}.response");

        var method = RequiredString(request, "method", $"{where}.request.method");
        var path = RequiredString(request, "path", $"{where}.request.path");
        if (!path.StartsWith('/'))
        {
            throw new InvalidOperationException(
                $"{where}.request.path must start with '/'");
        }

        string? body = null;
        if (request.TryGetProperty("body", out var bodyElement)
            && bodyElement.ValueKind != JsonValueKind.Null)
        {
            if (bodyElement.ValueKind != JsonValueKind.String)
            {
                throw new InvalidOperationException(
                    $"{where}.request.body must be a string");
            }

            body = bodyElement.GetString();
        }

        if (!response.TryGetProperty("status", out var statusElement)
            || !statusElement.TryGetInt32(out var status)
            || status is < 100 or > 599)
        {
            throw new InvalidOperationException(
                $"{where}.response.status must be an HTTP status");
        }

        var responseBody = RequiredString(
            response,
            "body",
            $"{where}.response.body",
            allowEmpty: true);
        return new Exchange(
            method,
            path,
            body,
            status,
            responseBody,
            readiness,
            readiness ? "runner readiness action" : "runner action");
    }

    private static void RequireObject(JsonElement value, string where)
    {
        if (value.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidOperationException($"{where} must be a JSON object");
        }
    }

    private static string RequiredString(
        JsonElement value,
        string property,
        string where,
        bool allowEmpty = false)
    {
        if (!value.TryGetProperty(property, out var field)
            || field.ValueKind != JsonValueKind.String
            || (!allowEmpty && string.IsNullOrEmpty(field.GetString())))
        {
            throw new InvalidOperationException(
                $"{where} must be {(allowEmpty ? "a string" : "a non-empty string")}");
        }

        return field.GetString()!;
    }

    private static void CheckKeys(
        JsonElement value,
        IReadOnlySet<string> allowed,
        string where)
    {
        var seen = new HashSet<string>();
        foreach (var property in value.EnumerateObject())
        {
            if (!seen.Add(property.Name))
            {
                throw new InvalidOperationException(
                    $"{where} repeats field: {property.Name}");
            }

            if (!allowed.Contains(property.Name))
            {
                throw new InvalidOperationException(
                    $"{where} has unknown field: {property.Name}");
            }
        }
    }

    private static string RequiredEnvironment(string variable) =>
        Environment.GetEnvironmentVariable(variable)
        ?? throw new InvalidOperationException($"{variable} is not set");

    private static string WithoutQuery(string path)
    {
        var query = path.IndexOf('?', StringComparison.Ordinal);
        return query == -1 ? path : path[..query];
    }
}
