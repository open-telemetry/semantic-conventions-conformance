/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.cassandra.CassandraScenario;

public final class CassandraJavaagentScenario {
  private CassandraJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Cassandra operation argument");
    }
    CassandraScenario.run(args[0], (session, contactPoints) -> session);
  }
}
