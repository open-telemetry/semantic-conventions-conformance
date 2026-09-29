/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.cassandra.v3;

import com.datastax.driver.core.BatchStatement;
import com.datastax.driver.core.Cluster;
import com.datastax.driver.core.PreparedStatement;
import com.datastax.driver.core.ResultSet;
import com.datastax.driver.core.Session;
import com.datastax.driver.core.SimpleStatement;
import com.datastax.driver.core.exceptions.InvalidQueryException;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;

/** Exercises the Cassandra driver 3 execution paths instrumented by the Java agent. */
public final class Cassandra3Scenario {
  private Cassandra3Scenario() {}

  public static void run(String operation) {
    try (Cluster cluster =
            Cluster.builder()
                .addContactPoint(ScenarioEnvironment.require("CASSANDRA_HOST"))
                .withPort(Integer.parseInt(ScenarioEnvironment.require("CASSANDRA_PORT")))
                .build();
        Session session = cluster.connect()) {
      switch (operation) {
        case "query":
          requireEmpty(session.execute("SELECT name FROM conformance.items WHERE id = 0"));
          break;
        case "prepared":
          prepared(session);
          break;
        case "batch":
          batch(session);
          break;
        case "error":
          error(session);
          break;
        default:
          throw new IllegalArgumentException("unknown Cassandra operation: " + operation);
      }
    }
  }

  private static void prepared(Session session) {
    PreparedStatement statement =
        session.prepare("SELECT name FROM conformance.items WHERE id = ?");
    requireEmpty(session.execute(statement.bind(-1)));
  }

  private static void batch(Session session) {
    BatchStatement statement =
        new BatchStatement()
            .add(
                new SimpleStatement(
                    "INSERT INTO conformance.items (id, name) VALUES (?, ?)", 1, "first"))
            .add(
                new SimpleStatement(
                    "INSERT INTO conformance.items (id, name) VALUES (?, ?)", 2, "second"));
    if (!session.execute(statement).wasApplied()) {
      throw new IllegalStateException("Cassandra batch was not applied");
    }
  }

  private static void error(Session session) {
    try {
      session.execute("SELECT * FROM conformance.missing_table");
    } catch (InvalidQueryException expected) {
      return;
    }
    throw new IllegalStateException("invalid Cassandra query unexpectedly succeeded");
  }

  private static void requireEmpty(ResultSet result) {
    if (!result.isExhausted()) {
      throw new IllegalStateException("Cassandra query returned an unexpected row");
    }
  }
}
