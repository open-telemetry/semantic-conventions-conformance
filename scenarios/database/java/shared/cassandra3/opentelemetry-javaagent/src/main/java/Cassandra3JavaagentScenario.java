/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.cassandra.v3.Cassandra3Scenario;

public final class Cassandra3JavaagentScenario {
  private Cassandra3JavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Cassandra operation argument");
    }
    Cassandra3Scenario.run(args[0]);
  }
}
