/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.vertxhttpclient;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import io.vertx.core.Vertx;
import io.vertx.core.http.HttpClient;
import io.vertx.core.http.HttpMethod;
import io.vertx.core.http.RequestOptions;

/** Runs the shared request contract through the Vert.x HTTP client. */
public final class VertxHttpClientClientScenario {
  private VertxHttpClientClientScenario() {}

  public static void run() throws Exception {
    Vertx vertx = Vertx.vertx();
    HttpClient client = vertx.createHttpClient();
    try {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) ->
              client
                  .request(
                      new RequestOptions()
                          .setAbsoluteURI(url)
                          .setMethod(HttpMethod.valueOf(method))
                          .putHeader("user-agent", HttpContract.USER_AGENT))
                  .compose(
                      request -> {
                        if (body != null) {
                          request.putHeader("content-type", HttpContract.CONTENT_TYPE);
                        }
                        return (body == null ? request.send() : request.send(body))
                            .compose(
                                response ->
                                    response
                                        .body()
                                        .map(
                                            buffer ->
                                                new HttpContract.Response(
                                                    response.statusCode(), buffer.toString())));
                      })
                  .toCompletionStage()
                  .toCompletableFuture()
                  .get());
    } finally {
      client.close();
      vertx.close().toCompletionStage().toCompletableFuture().get();
    }
  }
}
