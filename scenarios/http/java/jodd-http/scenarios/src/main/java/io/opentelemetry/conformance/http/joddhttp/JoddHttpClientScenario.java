/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.joddhttp;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import jodd.http.HttpRequest;
import jodd.http.HttpResponse;

/** Runs the shared request contract through Jodd HTTP. */
public final class JoddHttpClientScenario {
  private JoddHttpClientScenario() {}

  public static void run() throws Exception {
    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          HttpRequest request =
              new HttpRequest()
                  .method(method)
                  .set(url)
                  .header("user-agent", HttpContract.USER_AGENT);
          if (body != null) {
            request.contentType(HttpContract.CONTENT_TYPE).bodyText(body);
          }

          HttpResponse response = request.send();
          return new HttpContract.Response(response.statusCode(), response.bodyText());
        });
  }
}
