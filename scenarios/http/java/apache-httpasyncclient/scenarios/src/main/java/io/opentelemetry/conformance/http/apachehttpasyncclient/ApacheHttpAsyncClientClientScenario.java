/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.apachehttpasyncclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import org.apache.http.HttpEntity;
import org.apache.http.HttpResponse;
import org.apache.http.client.methods.RequestBuilder;
import org.apache.http.entity.ByteArrayEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.impl.nio.client.CloseableHttpAsyncClient;
import org.apache.http.impl.nio.client.HttpAsyncClients;
import org.apache.http.util.EntityUtils;

/** Runs the shared request contract through Apache HttpAsyncClient. */
public final class ApacheHttpAsyncClientClientScenario {
  private ApacheHttpAsyncClientClientScenario() {}

  public static void run() throws Exception {
    try (CloseableHttpAsyncClient client = HttpAsyncClients.createDefault()) {
      client.start();

      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            RequestBuilder request =
                RequestBuilder.create(method)
                    .setUri(URI.create(url))
                    .setHeader("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              request.setEntity(
                  new ByteArrayEntity(
                      body.getBytes(StandardCharsets.UTF_8),
                      ContentType.create(HttpContract.CONTENT_TYPE)));
            }

            HttpResponse response = client.execute(request.build(), null).get();
            HttpEntity entity = response.getEntity();
            return new HttpContract.Response(
                response.getStatusLine().getStatusCode(),
                entity == null ? "" : EntityUtils.toString(entity, StandardCharsets.UTF_8));
          });
    }
  }
}
