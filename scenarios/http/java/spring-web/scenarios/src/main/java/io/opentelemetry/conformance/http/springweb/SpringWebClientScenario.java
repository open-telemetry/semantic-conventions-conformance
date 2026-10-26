/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.springweb;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.util.function.Consumer;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

/** Runs the shared request contract through a Spring {@link RestTemplate}. */
public final class SpringWebClientScenario {
  private SpringWebClientScenario() {}

  public static void run(Consumer<RestTemplate> configureTelemetry) throws Exception {
    SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(HttpClientWorkload.REQUEST_TIMEOUT);
    requestFactory.setReadTimeout(HttpClientWorkload.REQUEST_TIMEOUT);
    RestTemplate restTemplate = new RestTemplate(requestFactory);
    restTemplate.setErrorHandler(response -> false);
    configureTelemetry.accept(restTemplate);

    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          HttpHeaders headers = new HttpHeaders();
          headers.set(HttpHeaders.USER_AGENT, HttpContract.USER_AGENT);
          if (body != null) {
            headers.set(HttpHeaders.CONTENT_TYPE, HttpContract.CONTENT_TYPE);
          }

          ResponseEntity<String> response =
              restTemplate.exchange(
                  url, HttpMethod.valueOf(method), new HttpEntity<>(body, headers), String.class);
          return new HttpContract.Response(
              response.getStatusCode().value(),
              response.getBody() == null ? "" : response.getBody());
        });
  }
}
