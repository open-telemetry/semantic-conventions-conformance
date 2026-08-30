/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.servlet3.Servlet3ServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.servlet.v3_0.ServletTelemetry;

public final class Servlet3LibraryServerScenario {
  private Servlet3LibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ServletTelemetry telemetry = ServletTelemetry.create(sdk.openTelemetry());
      Servlet3ServerScenario.run(telemetry.createFilter());
    }
  }
}
