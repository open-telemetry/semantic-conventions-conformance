/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.javahttpclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

/** Runs the shared request contract through the JDK's {@link HttpClient}. */
public final class JavaHttpClientClientScenario {
  private JavaHttpClientClientScenario() {}

  public static void run() throws Exception {
    HttpClient client = HttpClient.newBuilder().build();

    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          HttpRequest.Builder request =
              HttpRequest.newBuilder(URI.create(url))
                  .timeout(HttpClientWorkload.REQUEST_TIMEOUT)
                  .header("user-agent", HttpContract.USER_AGENT);
          if (body == null) {
            request.method(method, HttpRequest.BodyPublishers.noBody());
          } else {
            request
                .header("content-type", HttpContract.CONTENT_TYPE)
                .method(method, HttpRequest.BodyPublishers.ofString(body));
          }
          HttpResponse<String> response =
              client.send(request.build(), HttpResponse.BodyHandlers.ofString());
          return new HttpContract.Response(response.statusCode(), response.body());
        });
  }
}
