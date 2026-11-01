/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.json.JsonData;
import co.elastic.clients.transport.instrumentation.OpenTelemetryForElasticsearch;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import java.io.IOException;

public final class ElasticsearchApiClientScenario {
  private ElasticsearchApiClientScenario() {}

  public static void main(String[] args) throws IOException {
    String host = ScenarioEnvironment.require("DATABASE_HOST");
    int port = Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT"));
    String index = ScenarioEnvironment.require("DATABASE_NAME");

    try (ScenarioSdk sdk = ScenarioSdk.initialize();
        ElasticsearchClient client =
            ElasticsearchClient.of(
                config ->
                    config
                        .host("http://" + host + ":" + port)
                        .instrumentation(
                            new OpenTelemetryForElasticsearch(sdk.openTelemetry(), false)))) {
      SearchResponse<JsonData> response =
          client.search(
              search -> search.index(index).query(query -> query.matchAll(matchAll -> matchAll)),
              JsonData.class);
      if (response.timedOut()) {
        throw new IllegalStateException("Elasticsearch search timed out");
      }
      if (response.shards().failed().longValue() != 0) {
        throw new IllegalStateException("Elasticsearch search had failed shards");
      }
    }
  }
}
