/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.helidon.HelidonServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.helidon.v4_3.HelidonTelemetry;

public final class HelidonLibraryServerScenario {
  private HelidonLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      HelidonTelemetry telemetry = HelidonTelemetry.create(sdk.openTelemetry());
      HelidonServerScenario.run(routing -> routing.addFilter(telemetry.createFilter()));
    }
  }
}
