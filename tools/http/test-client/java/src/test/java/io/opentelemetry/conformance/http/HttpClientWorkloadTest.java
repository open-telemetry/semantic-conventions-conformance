/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.opentelemetry.conformance.http.HttpContract.Response;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class HttpClientWorkloadTest {

  private static final String BASE_URL = "http://127.0.0.1:0";

  /** A sender backed by the other side of the same contract, which is what a run measures. */
  private static List<String> driveAgainstTheContract() throws Exception {
    List<String> sent = new ArrayList<>();
    for (HttpContract.Exchange exchange : TestActions.REQUESTS) {
      HttpClientWorkload.drive(
          BASE_URL,
          (method, url, body) -> {
            String path = url.substring(BASE_URL.length());
            sent.add(method + " " + path);
            return HttpServerWorkload.respond(method, path, body, TestActions.EXCHANGES);
          },
          exchange);
    }
    return sent;
  }

  @Test
  void sendsEveryContractRequest() throws Exception {
    assertEquals(
        List.of(
            "GET /users/123",
            "GET /users/123?fields=name&verbose=true",
            "POST /items",
            "GET /status/404",
            "GET /status/500"),
        driveAgainstTheContract());
  }

  @Test
  void aResponseOutsideTheContractDoesNotFailTheScenario() throws Exception {
    HttpClientWorkload.drive(
        BASE_URL,
        (method, url, body) -> new Response(599, "not JSON"),
        TestActions.REQUESTS.get(0));
  }

  @Test
  void aNullResponseBodyDoesNotFailTheScenario() throws Exception {
    HttpClientWorkload.drive(
        BASE_URL, (method, url, body) -> new Response(200, null), TestActions.REQUESTS.get(0));
  }

  @Test
  void aBlankBaseUrlIsRefusedBeforeAnythingIsSent() {
    assertThrows(
        IllegalArgumentException.class,
        () ->
            HttpClientWorkload.drive(
                "  ", (method, url, body) -> new Response(200, "{}"), TestActions.REQUESTS.get(0)));
  }
}
