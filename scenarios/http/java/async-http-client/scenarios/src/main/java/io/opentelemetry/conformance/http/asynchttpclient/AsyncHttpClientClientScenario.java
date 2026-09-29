/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.asynchttpclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.util.concurrent.TimeUnit;
import org.asynchttpclient.AsyncHttpClient;
import org.asynchttpclient.DefaultAsyncHttpClient;
import org.asynchttpclient.RequestBuilder;
import org.asynchttpclient.Response;

/** Runs the shared request contract through Async HTTP Client. */
public final class AsyncHttpClientClientScenario {
  private AsyncHttpClientClientScenario() {}

  public static void run() throws Exception {
    try (AsyncHttpClient client = new DefaultAsyncHttpClient()) {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            RequestBuilder request =
                new RequestBuilder(method)
                    .setUrl(url)
                    .setHeader("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              request.setHeader("content-type", HttpContract.CONTENT_TYPE);
              request.setBody(body);
            }

            Response response =
                client
                    .executeRequest(request.build())
                    .get(HttpClientWorkload.REQUEST_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
            return new HttpContract.Response(response.getStatusCode(), response.getResponseBody());
          });
    }
  }
}
