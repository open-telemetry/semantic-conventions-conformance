/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static java.util.Objects.requireNonNull;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import io.opentelemetry.conformance.http.HttpContract.Response;
import java.io.ByteArrayInputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;

class HttpContractTest {

  @Test
  void itIsReadFromTheFileEveryLanguageReads() {
    assertFalse(HttpContract.exchanges().isEmpty());
  }

  @Test
  void theCombinedExchangesAreCachedWithTheContract() {
    assertSame(HttpContract.exchanges(), HttpContract.exchanges());
  }

  @Test
  void everyExchangeHasADescription() {
    assertTrue(
        HttpContract.exchanges().stream().map(Exchange::description).noneMatch(String::isBlank));
  }

  @Test
  void readinessIsNotMeasured() {
    List<Exchange> requests = HttpContract.requests();

    assertTrue(HttpContract.exchanges().stream().anyMatch(Exchange::readiness));
    assertTrue(requests.stream().noneMatch(Exchange::readiness));
    assertEquals(HttpContract.exchanges().size() - 1, requests.size());
  }

  @Test
  void aContractWithoutScenariosSaysSo() {
    ByteArrayInputStream contract =
        new ByteArrayInputStream("readiness: {}\n".getBytes(StandardCharsets.UTF_8));

    IllegalStateException failure =
        assertThrows(IllegalStateException.class, () -> HttpContract.load(contract));

    assertTrue(requireNonNull(failure.getMessage()).contains("declares no scenarios"));
  }

  @Test
  void eachOrdinalSelectsOneIndependentRequest() {
    for (int index = 0; index < HttpContract.requests().size(); index++) {
      assertEquals(HttpContract.requests().get(index), HttpContract.request(index));
    }
    assertThrows(IllegalArgumentException.class, () -> HttpContract.request(-1));
    assertThrows(
        IllegalArgumentException.class, () -> HttpContract.request(HttpContract.requests().size()));
  }

  @Test
  void aBlankResponseFailsCleanly() {
    Exchange exchange = HttpContract.request(0);

    assertThrows(
        IllegalStateException.class,
        () -> HttpContract.verify(exchange, new Response(exchange.status(), " ")));
  }

  // Parsed, not compared as text: whitespace and key order are a language's choice of JSON
  // writer, and neither is part of the contract.
  @Test
  void whitespaceAndKeyOrderAreTheJsonWritersBusiness() {
    Exchange users = HttpContract.exchange("GET", "/users/123").orElseThrow();

    assertDoesNotThrow(
        () ->
            HttpContract.verify(
                users, new Response(users.status(), "{ \"name\" :\"Alice\",\n  \"id\": 123 }")));
  }

  @Test
  void anAnswerThatIsNotJsonSaysSo() {
    Exchange users = HttpContract.exchange("GET", "/users/123").orElseThrow();

    UncheckedIOException failure =
        assertThrows(
            UncheckedIOException.class,
            () -> HttpContract.verify(users, new Response(users.status(), "<html>")));

    assertTrue(requireNonNull(failure.getMessage()).contains("did not return the expected JSON"));
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
