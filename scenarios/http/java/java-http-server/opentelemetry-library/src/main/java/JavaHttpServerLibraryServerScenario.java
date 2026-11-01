/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.javahttpserver.JavaHttpServerServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.javahttpserver.JavaHttpServerTelemetry;

public final class JavaHttpServerLibraryServerScenario {
  private JavaHttpServerLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      JavaHttpServerTelemetry telemetry = JavaHttpServerTelemetry.create(sdk.openTelemetry());
      JavaHttpServerServerScenario.run(telemetry::configure);
    }
  }
}
