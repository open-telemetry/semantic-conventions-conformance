/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ratpack.RatpackClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.ratpack.v1_7.RatpackClientTelemetry;
import io.opentelemetry.instrumentation.ratpack.v1_7.RatpackServerTelemetry;

public final class RatpackLibraryClientScenario {
  private RatpackLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      RatpackClientTelemetry telemetry = RatpackClientTelemetry.create(sdk.openTelemetry());
      RatpackServerTelemetry executionTelemetry =
          RatpackServerTelemetry.create(sdk.openTelemetry());
      RatpackClientScenario.run(telemetry::instrument, executionTelemetry.createExecInitializer());
    }
  }
}
