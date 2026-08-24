/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.springwebflux;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import org.springframework.http.HttpMethod;
import org.springframework.web.reactive.function.client.WebClient;

/** Runs the shared request contract through a Spring WebFlux {@link WebClient}. */
public final class SpringWebfluxClientScenario {
  private SpringWebfluxClientScenario() {}

  public static void run() throws Exception {
    WebClient client = WebClient.builder().build();

    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          WebClient.RequestBodySpec request =
              client
                  .method(HttpMethod.valueOf(method))
                  .uri(url)
                  .header("user-agent", HttpContract.USER_AGENT);
          WebClient.RequestHeadersSpec<?> requestHeaders = request;
          if (body != null) {
            requestHeaders =
                request.header("content-type", HttpContract.CONTENT_TYPE).bodyValue(body);
          }

          HttpContract.Response response =
              requestHeaders
                  .exchangeToMono(
                      received ->
                          received
                              .bodyToMono(String.class)
                              .defaultIfEmpty("")
                              .map(
                                  text ->
                                      new HttpContract.Response(
                                          received.statusCode().value(), text)))
                  .block();
          if (response == null) {
            throw new IllegalStateException("the WebClient completed without a response");
          }
          return response;
        });
  }
}
