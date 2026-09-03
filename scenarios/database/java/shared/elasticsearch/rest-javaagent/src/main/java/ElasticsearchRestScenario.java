/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.IOException;
import org.apache.http.HttpHost;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;

public final class ElasticsearchRestScenario {
  private ElasticsearchRestScenario() {}

  public static void main(String[] args) throws IOException {
    String host = ScenarioEnvironment.require("DATABASE_HOST");
    int port = Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT"));
    String index = ScenarioEnvironment.require("DATABASE_NAME");

    try (RestClient client = RestClient.builder(new HttpHost(host, port, "http")).build()) {
      Response response = client.performRequest(new Request("GET", "/" + index + "/_count"));
      if (response.getStatusLine().getStatusCode() != 200) {
        throw new IllegalStateException("Elasticsearch count returned " + response.getStatusLine());
      }
    }
  }
}
