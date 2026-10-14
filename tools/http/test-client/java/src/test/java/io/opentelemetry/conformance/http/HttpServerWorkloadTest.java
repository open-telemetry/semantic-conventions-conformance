/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import static org.junit.jupiter.api.Assertions.assertEquals;

import io.opentelemetry.conformance.http.HttpContract.Response;
import org.junit.jupiter.api.Test;

class HttpServerWorkloadTest {

  @Test
  void anAnswerComesFromTheContract() {
    Response answer = HttpServerWorkload.respond("GET", "/status/500", null, TestActions.EXCHANGES);

    assertEquals(500, answer.statusCode());
    assertEquals("{\"message\": \"status 500\"}", answer.body());
  }

  @Test
  void theRouteIsFoundThroughTheConcretePathTheFrameworkReports() {
    Response answer =
        HttpServerWorkload.respond("GET", "/users/123?fields=name", null, TestActions.EXCHANGES);

    assertEquals(200, answer.statusCode());
  }

  @Test
  void aScenarioThatNeverReadTheBodyWouldNotEchoIt() {
    Response answer =
        HttpServerWorkload.respond(
            "POST", "/items", "{\"name\": \"widget\"}", TestActions.EXCHANGES);

    assertEquals(201, answer.statusCode());
    assertEquals("{\"created\": true, \"payload\": {\"name\": \"widget\"}}", answer.body());
  }

  @Test
  void trafficTheContractDoesNotDescribeIsRefused() {
    Response answer = HttpServerWorkload.respond("GET", "/nope", null, TestActions.EXCHANGES);

    assertEquals(404, answer.statusCode());
  }
}
