/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.jettyhttpclient9;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.util.function.Supplier;
import org.eclipse.jetty.client.HttpClient;
import org.eclipse.jetty.client.api.ContentResponse;
import org.eclipse.jetty.client.api.Request;
import org.eclipse.jetty.client.util.StringContentProvider;

/** Runs the shared request contract through the Jetty 9 HTTP client. */
public final class JettyHttpClient9ClientScenario {
  private JettyHttpClient9ClientScenario() {}

  public static void run(Supplier<HttpClient> clientFactory) throws Exception {
    HttpClient client = clientFactory.get();
    client.start();
    try {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            Request request =
                client.newRequest(url).method(method).header("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              request.content(new StringContentProvider(body), HttpContract.CONTENT_TYPE);
            }
            ContentResponse response = request.send();
            return new HttpContract.Response(response.getStatus(), response.getContentAsString());
          });
    } finally {
      client.stop();
    }
  }
}
