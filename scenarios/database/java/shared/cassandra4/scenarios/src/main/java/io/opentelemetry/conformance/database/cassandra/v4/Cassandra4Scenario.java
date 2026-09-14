/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.cassandra.v4;

import com.datastax.oss.driver.api.core.CqlSession;
import com.datastax.oss.driver.api.core.cql.BatchStatement;
import com.datastax.oss.driver.api.core.cql.DefaultBatchType;
import com.datastax.oss.driver.api.core.cql.PreparedStatement;
import com.datastax.oss.driver.api.core.cql.ResultSet;
import com.datastax.oss.driver.api.core.cql.SimpleStatement;
import com.datastax.oss.driver.api.core.servererrors.InvalidQueryException;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.InetSocketAddress;
import java.util.function.UnaryOperator;

/** Exercises Cassandra driver 4 execution paths without choosing instrumentation. */
public final class Cassandra4Scenario {
  private Cassandra4Scenario() {}

  public static void run(String operation, UnaryOperator<CqlSession> instrumentSession) {
    CqlSession session =
        CqlSession.builder()
            .addContactPoint(
                new InetSocketAddress(
                    ScenarioEnvironment.require("CASSANDRA_HOST"),
                    Integer.parseInt(ScenarioEnvironment.require("CASSANDRA_PORT"))))
            .withLocalDatacenter(ScenarioEnvironment.require("CASSANDRA_LOCAL_DATACENTER"))
            .build();
    try (CqlSession instrumented = instrumentSession.apply(session)) {
      switch (operation) {
        case "query":
          requireEmpty(instrumented.execute("SELECT name FROM conformance.items WHERE id = 0"));
          break;
        case "prepared":
          prepared(instrumented);
          break;
        case "batch":
          batch(instrumented);
          break;
        case "error":
          error(instrumented);
          break;
        default:
          throw new IllegalArgumentException("unknown Cassandra operation: " + operation);
      }
    }
  }

  private static void prepared(CqlSession session) {
    PreparedStatement statement =
        session.prepare("SELECT name FROM conformance.items WHERE id = ?");
    requireEmpty(session.execute(statement.bind(-1)));
  }

  private static void batch(CqlSession session) {
    BatchStatement statement =
        BatchStatement.builder(DefaultBatchType.LOGGED)
            .addStatement(
                SimpleStatement.newInstance(
                    "INSERT INTO conformance.items (id, name) VALUES (?, ?)", 1, "first"))
            .addStatement(
                SimpleStatement.newInstance(
                    "INSERT INTO conformance.items (id, name) VALUES (?, ?)", 2, "second"))
            .build();
    if (!session.execute(statement).wasApplied()) {
      throw new IllegalStateException("Cassandra batch was not applied");
    }
  }

  private static void error(CqlSession session) {
    try {
      session.execute("SELECT * FROM conformance.missing_table");
    } catch (InvalidQueryException expected) {
      return;
    }
    throw new IllegalStateException("invalid Cassandra query unexpectedly succeeded");
  }

  private static void requireEmpty(ResultSet result) {
    if (result.one() != null) {
      throw new IllegalStateException("Cassandra query returned an unexpected row");
    }
  }
}
