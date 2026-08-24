/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.httpurlconnection;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

/** Runs the shared request contract through {@link HttpURLConnection}. */
public final class HttpUrlConnectionClientScenario {
  private HttpUrlConnectionClientScenario() {}

  public static void run() throws Exception {
    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          HttpURLConnection connection =
              (HttpURLConnection) URI.create(url).toURL().openConnection();
          try {
            int timeoutMillis = Math.toIntExact(HttpClientWorkload.REQUEST_TIMEOUT.toMillis());
            connection.setConnectTimeout(timeoutMillis);
            connection.setReadTimeout(timeoutMillis);
            connection.setRequestMethod(method);
            connection.setRequestProperty("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              byte[] requestBody = body.getBytes(StandardCharsets.UTF_8);
              connection.setDoOutput(true);
              connection.setRequestProperty("content-type", HttpContract.CONTENT_TYPE);
              connection.setFixedLengthStreamingMode(requestBody.length);
              try (OutputStream output = connection.getOutputStream()) {
                output.write(requestBody);
              }
            }

            int statusCode = connection.getResponseCode();
            // An error status arrives on the error stream rather than the input stream, and either
            // is null for a response that carried no body at all.
            try (InputStream input =
                statusCode >= 400 ? connection.getErrorStream() : connection.getInputStream()) {
              String responseBody =
                  input == null ? "" : new String(input.readAllBytes(), StandardCharsets.UTF_8);
              return new HttpContract.Response(statusCode, responseBody);
            }
          } finally {
            connection.disconnect();
          }
        });
  }
}
