// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Http.Tests;

internal static class TestActions
{
    internal const string Json =
        """
        [
          {"request":{"method":"GET","path":"/health"},"response":{"status":200,"body":"{\"ok\": true}"}},
          {"request":{"method":"GET","path":"/users/123"},"response":{"status":200,"body":"{\"id\": 123, \"name\": \"Alice\"}"}},
          {"request":{"method":"GET","path":"/users/123?fields=name&verbose=true"},"response":{"status":200,"body":"{\"id\": 123, \"name\": \"Alice\"}"}},
          {"request":{"method":"POST","path":"/items","body":"{\"name\": \"widget\"}"},"response":{"status":201,"body":"{\"created\": true, \"payload\": ${requestBody}}"}},
          {"request":{"method":"GET","path":"/status/404"},"response":{"status":404,"body":"{\"message\": \"status 404\"}"}},
          {"request":{"method":"GET","path":"/status/500"},"response":{"status":500,"body":"{\"message\": \"status 500\"}"}}
        ]
        """;

    internal static IReadOnlyList<HttpContract.Exchange> Exchanges { get; } =
        HttpContract.DeserializeActions(Json);

    internal static IReadOnlyList<HttpContract.Exchange> Requests { get; } =
        Exchanges.Skip(1).ToArray();
}
