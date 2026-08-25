/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.jettyhttpclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import org.eclipse.jetty.client.ContentResponse;
import org.eclipse.jetty.client.HttpClient;
import org.eclipse.jetty.client.Request;
import org.eclipse.jetty.client.StringRequestContent;

/** Runs the shared request contract through the Jetty HTTP client. */
public final class JettyHttpClientClientScenario {
  private JettyHttpClientClientScenario() {}

  public static void run() throws Exception {
    HttpClient client = new HttpClient();
    client.start();
    try {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            Request request = client.newRequest(url).method(method);
            request.headers(headers -> headers.put("user-agent", HttpContract.USER_AGENT));
            if (body != null) {
              request.body(new StringRequestContent(HttpContract.CONTENT_TYPE, body));
            }

            ContentResponse response = request.send();
            return new HttpContract.Response(response.getStatus(), response.getContentAsString());
          });
    } finally {
      client.stop();
    }
  }
}
