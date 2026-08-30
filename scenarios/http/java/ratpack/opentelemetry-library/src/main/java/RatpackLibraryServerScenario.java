/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ratpack.RatpackServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.ratpack.v1_7.RatpackServerTelemetry;

public final class RatpackLibraryServerScenario {
  private RatpackLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      RatpackServerTelemetry telemetry = RatpackServerTelemetry.create(sdk.openTelemetry());
      RatpackServerScenario.run(telemetry::configureRegistry);
    }
  }
}
