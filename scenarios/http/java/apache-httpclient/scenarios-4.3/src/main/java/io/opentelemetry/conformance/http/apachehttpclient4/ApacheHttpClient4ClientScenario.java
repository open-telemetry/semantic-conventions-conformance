/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.apachehttpclient4;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.nio.charset.StandardCharsets;
import java.util.function.Supplier;
import org.apache.http.client.config.RequestConfig;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpEntityEnclosingRequestBase;
import org.apache.http.entity.ContentType;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.util.EntityUtils;

/** Runs the shared request contract through Apache HttpClient 4. */
public final class ApacheHttpClient4ClientScenario {
  private ApacheHttpClient4ClientScenario() {}

  public static void run(Supplier<CloseableHttpClient> clientFactory) throws Exception {
    try (CloseableHttpClient client = clientFactory.get()) {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) -> {
            ContractRequest request = new ContractRequest(method, url);
            request.setConfig(
                RequestConfig.custom()
                    .setSocketTimeout((int) HttpClientWorkload.REQUEST_TIMEOUT.toMillis())
                    .build());
            request.addHeader("user-agent", HttpContract.USER_AGENT);
            if (body != null) {
              request.setEntity(
                  new StringEntity(
                      body, ContentType.create(HttpContract.CONTENT_TYPE, StandardCharsets.UTF_8)));
            }
            try (CloseableHttpResponse response = client.execute(request)) {
              return new HttpContract.Response(
                  response.getStatusLine().getStatusCode(),
                  response.getEntity() == null ? "" : EntityUtils.toString(response.getEntity()));
            }
          });
    }
  }

  private static final class ContractRequest extends HttpEntityEnclosingRequestBase {
    private final String method;

    ContractRequest(String method, String url) {
      this.method = method;
      setURI(java.net.URI.create(url));
    }

    @Override
    public String getMethod() {
      return method;
    }
  }
}
