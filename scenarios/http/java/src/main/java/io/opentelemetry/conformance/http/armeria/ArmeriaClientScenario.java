/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package io.opentelemetry.conformance.http.armeria;

import com.linecorp.armeria.client.WebClient;
import com.linecorp.armeria.common.HttpData;
import com.linecorp.armeria.common.HttpMethod;
import com.linecorp.armeria.common.HttpRequest;
import com.linecorp.armeria.common.RequestHeaders;
import io.opentelemetry.conformance.http.HttpTestClient;
import io.opentelemetry.instrumentation.armeria.v1_3.ArmeriaClientTelemetry;
import java.net.URI;

/** Runs the shared request contract through an Armeria {@link WebClient}. */
public final class ArmeriaClientScenario {
  private ArmeriaClientScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("usage: ArmeriaClientScenario <agent|library>");
    }
    String baseUrl = ScenarioTelemetry.requireEnvironment("MOCK_SERVER_URL");

    try (ScenarioTelemetry telemetry = ScenarioTelemetry.initialize(args[0])) {
      WebClient client =
          telemetry.isLibrary()
              ? WebClient.builder(baseUrl)
                  .decorator(
                      ArmeriaClientTelemetry.create(telemetry.openTelemetry())
                          .createDecorator())
                  .build()
              : WebClient.of(baseUrl);

      HttpTestClient.drive(
          baseUrl,
          (method, url, body) -> {
            URI uri = URI.create(url);
            String path = uri.getRawPath();
            if (uri.getRawQuery() != null) {
              path += "?" + uri.getRawQuery();
            }
            RequestHeaders headers =
                body == null
                    ? RequestHeaders.of(HttpMethod.valueOf(method), path)
                    : RequestHeaders.builder(HttpMethod.valueOf(method), path)
                        .add("content-type", "application/json")
                        .build();
            HttpRequest request =
                body == null
                    ? HttpRequest.of(headers)
                    : HttpRequest.of(headers, HttpData.ofUtf8(body));
            var response = client.execute(request).aggregate().join();
            return new HttpTestClient.Response(
                response.status().code(), response.contentUtf8());
          });
    }
  }
}
