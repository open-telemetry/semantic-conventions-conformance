/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.apache.hc.core5.http.HttpHost;
import org.opensearch.client.Request;
import org.opensearch.client.Response;
import org.opensearch.client.RestClient;

@SuppressWarnings("deprecation")
public final class OpenSearchRest3JavaagentScenario {
  private OpenSearchRest3JavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one OpenSearch operation argument");
    }

    try (RestClient client =
        RestClient.builder(
                new HttpHost(
                    "http",
                    ScenarioEnvironment.require("DATABASE_HOST"),
                    Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT"))))
            .build()) {
      run(client, args[0]);
    }
  }

  private static void run(RestClient client, String operation) throws IOException {
    switch (operation) {
      case "cluster_health":
        requireContains(perform(client, new Request("GET", "/_cluster/health")), "\"status\"");
        break;
      case "get_document":
        requireContains(
            perform(client, new Request("GET", "/conformance/_doc/1")), "\"found\":true");
        break;
      case "search":
        Request request = new Request("POST", "/conformance/_search");
        request.setJsonEntity("{\"query\":{\"term\":{\"name\":\"alpha\"}}}");
        requireContains(perform(client, request), "\"_id\":\"1\"");
        break;
      default:
        throw new IllegalArgumentException("unknown OpenSearch operation: " + operation);
    }
  }

  private static String perform(RestClient client, Request request) throws IOException {
    Response response = client.performRequest(request);
    if (response.getStatusLine().getStatusCode() != 200) {
      throw new IllegalStateException(
          "OpenSearch returned " + response.getStatusLine().getStatusCode());
    }
    return new String(response.getEntity().getContent().readAllBytes(), StandardCharsets.UTF_8);
  }

  private static void requireContains(String response, String expected) {
    if (!response.contains(expected)) {
      throw new IllegalStateException("OpenSearch response did not contain " + expected);
    }
  }
}
