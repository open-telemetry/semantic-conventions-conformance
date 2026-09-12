/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

/** What the runner told a scenario, in the one place a scenario reads it. */
public final class ScenarioEnvironment {
  private ScenarioEnvironment() {}

  /** The value of {@code name}, or a failure naming what was missing. */
  public static String require(String name) {
    String value = System.getenv(name);
    if (value == null || value.isBlank()) {
      throw new IllegalStateException("required environment variable is missing: " + name);
    }
    return value;
  }

  /** The value of {@code name}, or {@code defaultValue} when it is missing or blank. */
  public static String getOrDefault(String name, String defaultValue) {
    String value = System.getenv(name);
    return value == null || value.isBlank() ? defaultValue : value;
  }
}
