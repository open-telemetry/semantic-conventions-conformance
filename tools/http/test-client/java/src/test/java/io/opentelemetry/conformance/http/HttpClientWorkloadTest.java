/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static java.util.Objects.requireNonNull;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import io.opentelemetry.conformance.http.HttpContract.Response;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class HttpClientWorkloadTest {

  private static final String BASE_URL = "http://127.0.0.1:0";

  /** A sender backed by the other side of the same contract, which is what a run measures. */
  private static List<String> driveAgainstTheContract() throws Exception {
    List<String> sent = new ArrayList<>();
    HttpClientWorkload.drive(
        BASE_URL,
        (method, url, body) -> {
          String path = url.substring(BASE_URL.length());
          sent.add(method + " " + path);
          return HttpServerWorkload.respond(method, path, body);
        });
    return sent;
  }

  @Test
  void bothSidesOfTheContractAgree() throws Exception {
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
  void aWrongStatusFailsTheRun() {
    Exchange users = HttpContract.exchange("GET", "/users/123").orElseThrow();

    ContractError failure =
        assertThrows(
            ContractError.class,
            () -> HttpClientWorkload.verify(users, new Response(500, users.responseBody())));
    assertTrue(requireNonNull(failure.getMessage()).contains("answered 500"));
  }

  @Test
  void whitespaceAndKeyOrderAreTheJsonWritersBusiness() {
    Exchange users = HttpContract.exchange("GET", "/users/123").orElseThrow();

    HttpClientWorkload.verify(
        users, new Response(users.status(), "{ \"name\" :\"Alice\",\n  \"id\": 123 }"));
  }

  @Test
  void anAnswerThatIsNotJsonSaysSo() {
    Exchange users = HttpContract.exchange("GET", "/users/123").orElseThrow();

    ContractError failure =
        assertThrows(
            ContractError.class,
            () -> HttpClientWorkload.verify(users, new Response(users.status(), "<html>")));

    assertTrue(requireNonNull(failure.getMessage()).startsWith("not JSON"));
  }

  @Test
  void aBlankBaseUrlIsRefusedBeforeAnythingIsSent() {
    assertThrows(
        IllegalArgumentException.class,
        () -> HttpClientWorkload.drive("  ", (method, url, body) -> new Response(200, "{}")));
  }
}
