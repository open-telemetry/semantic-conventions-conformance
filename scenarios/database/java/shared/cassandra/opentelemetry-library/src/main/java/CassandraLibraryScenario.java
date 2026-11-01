/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.cassandra.CassandraScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.cassandra.v4_4.CassandraTelemetry;

public final class CassandraLibraryScenario {
  private CassandraLibraryScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Cassandra operation argument");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      CassandraTelemetry telemetry = CassandraTelemetry.create(sdk.openTelemetry());
      CassandraScenario.run(args[0], telemetry::wrap);
    }
  }
}
