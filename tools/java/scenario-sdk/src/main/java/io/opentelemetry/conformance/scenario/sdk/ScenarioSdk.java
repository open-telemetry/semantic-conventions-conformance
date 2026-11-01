/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario.sdk;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.autoconfigure.AutoConfiguredOpenTelemetrySdk;

/**
 * The OpenTelemetry SDK a scenario configures for itself.
 *
 * <p>Only a scenario measuring explicit library instrumentation needs this. An agent scenario has
 * its SDK configured for it, and must not carry these jars on its classpath at all.
 */
public final class ScenarioSdk implements AutoCloseable {
  private static final long FLUSH_TIMEOUT_MILLIS = 15_000;

  private final OpenTelemetrySdk openTelemetrySdk;

  /** Autoconfigures the SDK, failing early rather than exporting nowhere. */
  public static ScenarioSdk initialize() {
    ScenarioEnvironment.require("OTEL_EXPORTER_OTLP_ENDPOINT");
    return new ScenarioSdk(AutoConfiguredOpenTelemetrySdk.initialize().getOpenTelemetrySdk());
  }

  private ScenarioSdk(OpenTelemetrySdk openTelemetrySdk) {
    this.openTelemetrySdk = openTelemetrySdk;
  }

  public OpenTelemetry openTelemetry() {
    return openTelemetrySdk;
  }

  @Override
  public void close() {
    try {
      TelemetryLifecycle.flushBeforeShutdown(
          openTelemetrySdk.getSdkTracerProvider()::forceFlush,
          openTelemetrySdk.getSdkLoggerProvider()::forceFlush,
          openTelemetrySdk.getSdkMeterProvider()::forceFlush,
          FLUSH_TIMEOUT_MILLIS);
    } finally {
      openTelemetrySdk.close();
    }
  }
}
