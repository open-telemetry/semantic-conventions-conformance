/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.okhttp;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/** Runs the shared request contract through an {@link OkHttpClient}. */
public final class OkHttpClientScenario {

  private static final MediaType JSON = MediaType.get(HttpContract.CONTENT_TYPE);

  private OkHttpClientScenario() {}

  public static void run() throws Exception {
    OkHttpClient client = new OkHttpClient.Builder().build();

    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          Request.Builder request =
              new Request.Builder().url(url).header("user-agent", HttpContract.USER_AGENT);
          if (body == null) {
            request.method(method, null);
          } else {
            request
                .header("content-type", HttpContract.CONTENT_TYPE)
                .method(method, RequestBody.create(body, JSON));
          }
          try (Response response = client.newCall(request.build()).execute()) {
            ResponseBody responseBody = response.body();
            return new HttpContract.Response(
                response.code(), responseBody == null ? "" : responseBody.string());
          }
        });
  }
}
