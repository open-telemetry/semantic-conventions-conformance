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
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one JDBC operation argument");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      OpenTelemetryDriver.install(sdk.openTelemetry());
      JdbcScenario.run(args[0]);
    }
  }
}
