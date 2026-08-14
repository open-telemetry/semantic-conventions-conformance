/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import java.util.List;
import org.junit.jupiter.api.Test;

class HttpContractTest {

  @Test
  void itIsReadFromTheFileEveryLanguageReads() {
    assertFalse(HttpContract.exchanges().isEmpty());
  }

  @Test
  void readinessIsNotMeasured() {
    List<Exchange> requests = HttpContract.requests();

    assertTrue(HttpContract.exchanges().stream().anyMatch(Exchange::readiness));
    assertTrue(requests.stream().noneMatch(Exchange::readiness));
    assertEquals(HttpContract.exchanges().size() - 1, requests.size());
  }

  @Test
  void aQueryStringDoesNotChangeWhichExchangeAnswers() {
    Exchange plain = HttpContract.exchange("GET", "/users/123").orElseThrow();
    Exchange withQuery =
        HttpContract.exchange("GET", "/users/123?fields=name&verbose=true").orElseThrow();

    assertEquals(plain.status(), withQuery.status());
    assertEquals(plain.responseBody(), withQuery.responseBody());
  }

  @Test
  void theMethodIsPartOfTheLookup() {
    assertTrue(HttpContract.exchange("DELETE", "/items").isEmpty());
  }

  @Test
  void anUnknownPathDescribesNoExchange() {
    assertTrue(HttpContract.exchange("GET", "/nope").isEmpty());
  }

  @Test
  void theBodyThatArrivedIsWhatIsEchoed() {
    Exchange items = HttpContract.exchange("POST", "/items").orElseThrow();

    assertEquals(
        "{\"created\": true, \"payload\": {\"name\": \"widget\"}}",
        items.renderResponseBody("{\"name\": \"widget\"}"));
  }

  @Test
  void aRequestThatCarriedNoBodyEchoesAnEmptyObject() {
    Exchange items = HttpContract.exchange("POST", "/items").orElseThrow();

    assertEquals(items.renderResponseBody(null), items.renderResponseBody(""));
    assertEquals("{\"created\": true, \"payload\": {}}", items.renderResponseBody(null));
  }
}
