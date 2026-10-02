/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.IOException;
import java.util.Map;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;

public final class ElasticsearchApiClientScenario {
  private ElasticsearchApiClientScenario() {}

  public static void main(String[] args) throws IOException {
    String host = ScenarioEnvironment.require("DATABASE_HOST");
    int port = Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT"));
    String index = ScenarioEnvironment.require("DATABASE_NAME");

    try (RestClient restClient = RestClient.builder(new HttpHost(host, port, "http")).build();
        ElasticsearchTransport transport =
            new RestClientTransport(restClient, new JacksonJsonpMapper())) {
      ElasticsearchClient client = new ElasticsearchClient(transport);
      SearchResponse<Map> response =
          client.search(
              search -> search.index(index).query(query -> query.matchAll(matchAll -> matchAll)),
              Map.class);
      if (response.timedOut()) {
        throw new IllegalStateException("Elasticsearch search timed out");
      }
    }
  }
}
