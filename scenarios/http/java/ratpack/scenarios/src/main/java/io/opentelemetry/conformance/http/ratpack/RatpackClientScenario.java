/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.ratpack;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.URI;
import ratpack.http.client.HttpClient;
import ratpack.test.exec.ExecHarness;

/**
 * Runs the shared request contract through Ratpack's {@link HttpClient}.
 *
 * <p>Ratpack's client hands back a promise that only resolves inside an execution, so the requests
 * are driven through an {@link ExecHarness} — the supported way to run one outside a server.
 */
public final class RatpackClientScenario {
  private RatpackClientScenario() {}

  public static void run() throws Exception {
    try (ExecHarness harness = ExecHarness.harness();
        HttpClient client = HttpClient.of(spec -> spec.execController(harness.getController()))) {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) ->
              harness
                  .yield(
                      execution ->
                          client
                              .request(
                                  URI.create(url),
                                  request -> {
                                    request.method(method);
                                    request.headers(
                                        headers -> {
                                          headers.set("user-agent", HttpContract.USER_AGENT);
                                          if (body != null) {
                                            headers.set("content-type", HttpContract.CONTENT_TYPE);
                                          }
                                        });
                                    if (body != null) {
                                      request.body(content -> content.text(body));
                                    }
                                  })
                              // Read inside the execution: the buffer backing the response is
                              // released as soon as it ends.
                              .map(
                                  response ->
                                      new HttpContract.Response(
                                          response.getStatus().getCode(),
                                          response.getBody().getText())))
                  .getValueOrThrow());
    }
  }
}
