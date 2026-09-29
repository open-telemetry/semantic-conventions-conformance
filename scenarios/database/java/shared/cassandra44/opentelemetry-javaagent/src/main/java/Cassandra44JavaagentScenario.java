/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.cassandra.v4.Cassandra4Scenario;
import java.util.function.UnaryOperator;

public final class Cassandra44JavaagentScenario {
  private Cassandra44JavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Cassandra operation argument");
    }
    Cassandra4Scenario.run(args[0], UnaryOperator.identity());
  }
}
