/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.InetAddress;
import java.net.UnknownHostException;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.transport.TransportClient;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.common.transport.TransportAddress;
import org.elasticsearch.transport.client.PreBuiltTransportClient;

public final class ElasticsearchTransportScenario {
  private ElasticsearchTransportScenario() {}

  public static void main(String[] args) throws UnknownHostException {
    String host = ScenarioEnvironment.require("DATABASE_HOST");
    int port = Integer.parseInt(ScenarioEnvironment.require("DATABASE_TRANSPORT_PORT"));
    String index = ScenarioEnvironment.require("DATABASE_NAME");
    Settings settings =
        Settings.builder()
            .put("cluster.name", "docker-cluster")
            .put("client.transport.sniff", false)
            .build();

    try (TransportClient client = new PreBuiltTransportClient(settings)) {
      client.addTransportAddress(new TransportAddress(InetAddress.getByName(host), port));
      SearchResponse response = client.prepareSearch(index).setSize(0).get();
      if (response.isTimedOut()) {
        throw new IllegalStateException("Elasticsearch transport search timed out");
      }
    }
  }
}
