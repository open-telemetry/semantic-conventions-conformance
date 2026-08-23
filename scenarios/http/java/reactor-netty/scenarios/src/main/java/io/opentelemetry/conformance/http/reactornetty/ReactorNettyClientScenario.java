/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.reactornetty;

import io.netty.handler.codec.http.HttpMethod;
import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

/** Runs the shared request contract through the Reactor Netty HTTP client. */
public final class ReactorNettyClientScenario {
  private ReactorNettyClientScenario() {}

  public static void run() throws Exception {
    HttpClient client =
        HttpClient.create().headers(headers -> headers.set("user-agent", HttpContract.USER_AGENT));

    HttpClientWorkload.drive(
        ScenarioEnvironment.require("MOCK_SERVER_URL"),
        (method, url, body) -> {
          HttpClient.RequestSender sender =
              client
                  .headers(
                      headers -> {
                        if (body != null) {
                          headers.set("content-type", HttpContract.CONTENT_TYPE);
                        }
                      })
                  .request(HttpMethod.valueOf(method))
                  .uri(url);
          HttpClient.ResponseReceiver<?> receiver =
              body == null
                  ? sender
                  : sender.send((request, out) -> out.sendString(Mono.just(body)));

          HttpContract.Response response =
              receiver
                  .responseSingle(
                      (status, content) ->
                          content
                              .asString()
                              .defaultIfEmpty("")
                              .map(text -> new HttpContract.Response(status.status().code(), text)))
                  .block();
          if (response == null) {
            throw new IllegalStateException(
                "the Reactor Netty client completed without a response");
          }
          return response;
        });
  }
}
