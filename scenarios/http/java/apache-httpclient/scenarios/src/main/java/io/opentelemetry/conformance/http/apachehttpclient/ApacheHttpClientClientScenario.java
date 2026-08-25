/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.apachehttpclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.nio.charset.StandardCharsets;
import org.apache.hc.client5.http.classic.methods.HttpUriRequestBase;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.ContentType;
import org.apache.hc.core5.http.io.entity.ByteArrayEntity;
import org.apache.hc.core5.http.io.entity.EntityUtils;
import org.apache.hc.core5.util.Timeout;

/** Runs the shared request contract through Apache HttpClient 5's classic API. */
public final class ApacheHttpClientClientScenario {
  private ApacheHttpClientClientScenario() {}

  public static void run() throws Exception {
    try (CloseableHttpClient client = HttpClients.createDefault()) {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            HttpUriRequestBase request = new HttpUriRequestBase(method, java.net.URI.create(url));
            request.setConfig(
                RequestConfig.custom()
                    .setResponseTimeout(
                        Timeout.ofMilliseconds(HttpClientWorkload.REQUEST_TIMEOUT.toMillis()))
                    .build());
            request.addHeader("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              request.setEntity(
                  new ByteArrayEntity(
                      body.getBytes(StandardCharsets.UTF_8),
                      ContentType.parse(HttpContract.CONTENT_TYPE)));
            }
            return client.execute(
                request,
                response ->
                    new HttpContract.Response(
                        response.getCode(),
                        response.getEntity() == null
                            ? ""
                            : EntityUtils.toString(response.getEntity())));
          });
    }
  }
}
