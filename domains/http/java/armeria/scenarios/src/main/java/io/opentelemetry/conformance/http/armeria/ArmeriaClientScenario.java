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
import com.linecorp.armeria.common.RequestHeadersBuilder;
import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.URI;
import java.util.function.Function;

/** Runs the shared request contract through an Armeria {@link WebClient}. */
public final class ArmeriaClientScenario {
  private ArmeriaClientScenario() {}

  /** Runs it through a plain client, for a scenario whose instrumentation attaches itself. */
  public static void run() throws Exception {
    run(WebClient::of);
  }

  public static void run(Function<String, WebClient> clientFactory) throws Exception {
    String baseUrl = ScenarioEnvironment.require("MOCK_SERVER_URL");
    URI mockServerUri = URI.create(baseUrl);
    if (!"http".equals(mockServerUri.getScheme()) || mockServerUri.getRawAuthority() == null) {
      throw new IllegalArgumentException("MOCK_SERVER_URL must be an http:// URL: " + baseUrl);
    }
    WebClient client = clientFactory.apply("h1c://" + mockServerUri.getRawAuthority());

    HttpClientWorkload.drive(
        baseUrl,
        (method, url, body) -> {
          URI uri = URI.create(url);
          String path = uri.getRawPath();
          if (uri.getRawQuery() != null) {
            path += "?" + uri.getRawQuery();
          }
          RequestHeadersBuilder headers =
              RequestHeaders.builder(HttpMethod.valueOf(method), path)
                  .add("user-agent", HttpContract.USER_AGENT);
          if (body != null) {
            headers.add("content-type", HttpContract.CONTENT_TYPE);
          }
          HttpRequest request =
              body == null
                  ? HttpRequest.of(headers.build())
                  : HttpRequest.of(headers.build(), HttpData.ofUtf8(body));
          var response = client.execute(request).aggregate().join();
          return new HttpContract.Response(response.status().code(), response.contentUtf8());
        });
  }
}
