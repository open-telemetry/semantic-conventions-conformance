/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.servlet.ServletServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.servlet.v5_0.ServletTelemetry;

public final class Servlet5LibraryServerScenario {
  private Servlet5LibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ServletTelemetry telemetry = ServletTelemetry.create(sdk.openTelemetry());
      ServletServerScenario.run(telemetry.createFilter());
    }
  }
}
