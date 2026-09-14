/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.cassandra.v4.Cassandra4Scenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.cassandra.v4_4.CassandraTelemetry;

public final class Cassandra44LibraryScenario {
  private Cassandra44LibraryScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Cassandra operation argument");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      CassandraTelemetry telemetry = CassandraTelemetry.create(sdk.openTelemetry());
      Cassandra4Scenario.run(args[0], telemetry::wrap);
    }
  }
}
