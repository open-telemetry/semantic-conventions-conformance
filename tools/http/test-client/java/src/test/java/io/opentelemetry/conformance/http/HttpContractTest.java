/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import java.util.List;
import org.junit.jupiter.api.Test;

class HttpContractTest {

  @Test
  void completeActionTableIncludesReadinessAndMeasuredRequests() {
    List<Exchange> exchanges = HttpContract.loadActions(TestActions.JSON);

    assertTrue(exchanges.get(0).readiness());
    assertTrue(exchanges.stream().skip(1).noneMatch(Exchange::readiness));
    assertEquals(6, exchanges.size());
  }

  @Test
  void singularClientActionIsDecoded() {
    Exchange exchange =
        HttpContract.loadAction(
            "{\"request\":{\"method\":\"POST\",\"path\":\"/items\",\"body\":\"{}\"},"
                + "\"response\":{\"status\":201,\"body\":\"{}\"}}");

    assertEquals("POST", exchange.method());
    assertEquals("/items", exchange.path());
    assertEquals("{}", exchange.body());
    assertEquals(201, exchange.status());
  }

  @Test
  void missingSelectedActionNamesTheVariable() {
    IllegalStateException failure =
        assertThrows(IllegalStateException.class, HttpContract::scenarioRequest);

    assertEquals(HttpContract.ACTION_VARIABLE + " is not set", failure.getMessage());
  }

  @Test
  void malformedJsonAndUnknownFieldsAreRejected() {
    assertTrue(
        assertThrows(IllegalStateException.class, () -> HttpContract.loadAction("{"))
            .getMessage()
            .contains("malformed JSON"));
    assertTrue(
        assertThrows(
                IllegalStateException.class,
                () -> HttpContract.loadAction("{\"request\":{},\"response\":{},\"extra\":true}"))
            .getMessage()
            .contains("unknown field"));
  }

  @Test
  void malformedAndEmptyActionTablesAreRejected() {
    assertThrows(IllegalStateException.class, () -> HttpContract.loadActions("not JSON"));
    assertThrows(IllegalStateException.class, () -> HttpContract.loadActions("[]"));
  }

  @Test
  void requestAndResponseLookupPreservesMethodQueryAndBodyHandling() {
    Exchange plain =
        HttpContract.exchange(TestActions.EXCHANGES, "GET", "/users/123").orElseThrow();
    Exchange withQuery =
        HttpContract.exchange(TestActions.EXCHANGES, "GET", "/users/123?fields=name&verbose=true")
            .orElseThrow();
    Exchange items = HttpContract.exchange(TestActions.EXCHANGES, "POST", "/items").orElseThrow();

    assertEquals(plain.status(), withQuery.status());
    assertFalse(HttpContract.exchange(TestActions.EXCHANGES, "DELETE", "/items").isPresent());
    assertEquals(
        "{\"created\": true, \"payload\": {\"name\": \"widget\"}}",
        items.renderResponseBody("{\"name\": \"widget\"}"));
  }
}
