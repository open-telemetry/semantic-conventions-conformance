/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.IOException;
import org.apache.hc.core5.http.HttpHost;
import org.opensearch.client.json.JsonData;
import org.opensearch.client.json.jackson.JacksonJsonpMapper;
import org.opensearch.client.opensearch.OpenSearchClient;
import org.opensearch.client.opensearch.core.GetResponse;
import org.opensearch.client.opensearch.core.SearchResponse;
import org.opensearch.client.transport.OpenSearchTransport;
import org.opensearch.client.transport.httpclient5.ApacheHttpClient5TransportBuilder;

public final class OpenSearchJava3JavaagentScenario {
  private OpenSearchJava3JavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one OpenSearch operation argument");
    }

    HttpHost host =
        new HttpHost(
            "http",
            ScenarioEnvironment.require("DATABASE_HOST"),
            Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT")));
    try (OpenSearchTransport transport =
        ApacheHttpClient5TransportBuilder.builder(host)
            .setMapper(new JacksonJsonpMapper())
            .build()) {
      run(new OpenSearchClient(transport), args[0]);
    }
  }

  private static void run(OpenSearchClient client, String operation) throws IOException {
    switch (operation) {
      case "cluster_health":
        if (client.cluster().health() == null) {
          throw new IllegalStateException("OpenSearch returned no cluster health response");
        }
        break;
      case "get_document":
        GetResponse<JsonData> get =
            client.get(request -> request.index("conformance").id("1"), JsonData.class);
        if (!get.found()) {
          throw new IllegalStateException("OpenSearch did not return document 1");
        }
        break;
      case "search":
        SearchResponse<JsonData> search =
            client.search(
                request ->
                    request
                        .index("conformance")
                        .query(
                            query ->
                                query.term(
                                    term ->
                                        term.field("name")
                                            .value(value -> value.stringValue("alpha")))),
                JsonData.class);
        if (search.hits().hits().stream().noneMatch(hit -> "1".equals(hit.id()))) {
          throw new IllegalStateException("OpenSearch search did not return document 1");
        }
        break;
      default:
        throw new IllegalArgumentException("unknown OpenSearch operation: " + operation);
    }
  }
}
