/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.sdk.autoconfigure.AutoConfiguredOpenTelemetrySdk;

final class ScenarioTelemetry implements AutoCloseable {
  private final AutoConfiguredOpenTelemetrySdk configuredSdk;

  private ScenarioTelemetry(AutoConfiguredOpenTelemetrySdk configuredSdk) {
    this.configuredSdk = configuredSdk;
  }

  static ScenarioTelemetry initialize(String mode) {
    requireEnvironment("OTEL_EXPORTER_OTLP_ENDPOINT");
    return switch (mode) {
      case "agent" -> new ScenarioTelemetry(null);
      case "library" -> new ScenarioTelemetry(AutoConfiguredOpenTelemetrySdk.initialize());
      default ->
          throw new IllegalArgumentException(
              "instrumentation mode must be 'agent' or 'library', not: " + mode);
    };
  }

  boolean isLibrary() {
    return configuredSdk != null;
  }

  OpenTelemetry openTelemetry() {
    if (configuredSdk == null) {
      throw new IllegalStateException("library telemetry is unavailable in agent mode");
    }
    return configuredSdk.getOpenTelemetrySdk();
  }

  @Override
  public void close() {
    if (configuredSdk != null) {
      configuredSdk.getOpenTelemetrySdk().close();
    }
  }

  static String requireEnvironment(String name) {
    String value = System.getenv(name);
    if (value == null || value.isBlank()) {
      throw new IllegalStateException("required environment variable is missing: " + name);
    }
    return value;
  }
}
