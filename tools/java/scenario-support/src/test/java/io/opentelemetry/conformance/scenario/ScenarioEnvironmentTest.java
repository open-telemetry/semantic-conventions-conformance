/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.UUID;
import org.junit.jupiter.api.Test;

class ScenarioEnvironmentTest {
  @Test
  void acceptsPresentEmptyValues() {
    assertEquals("", ScenarioEnvironment.requirePresent("OTEL_CONFORMANCE_TEST_EMPTY"));
    assertEquals(" ", ScenarioEnvironment.requirePresent("OTEL_CONFORMANCE_TEST_WHITESPACE"));
  }

  @Test
  void stillRejectsBlankRequiredValues() {
    assertThrows(
        IllegalStateException.class,
        () -> ScenarioEnvironment.require("OTEL_CONFORMANCE_TEST_EMPTY"));
    assertThrows(
        IllegalStateException.class,
        () -> ScenarioEnvironment.require("OTEL_CONFORMANCE_TEST_WHITESPACE"));
  }

  @Test
  void rejectsAbsentValues() {
    String name = "OTEL_CONFORMANCE_MISSING_" + UUID.randomUUID();
    IllegalStateException error =
        assertThrows(IllegalStateException.class, () -> ScenarioEnvironment.requirePresent(name));
    assertEquals("required environment variable is missing: " + name, error.getMessage());
  }
}
