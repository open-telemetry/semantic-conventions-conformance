/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.jdbc.JdbcScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.jdbc.OpenTelemetryDriver;

public final class JdbcLibraryScenario {
  private JdbcLibraryScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 0) {
      throw new IllegalArgumentException("expected no JDBC operation arguments");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      OpenTelemetryDriver.install(sdk.openTelemetry());
      JdbcScenario.run();
    }
  }
}
