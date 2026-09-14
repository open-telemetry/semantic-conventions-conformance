/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.jdbc;

import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Arrays;

/** Exercises individual JDBC execution paths against a relational database. */
public final class JdbcScenario {
  private JdbcScenario() {}

  public static void run(String operation) throws SQLException {
    try (Connection connection =
        DriverManager.getConnection(
            ScenarioEnvironment.require("JDBC_URL"),
            ScenarioEnvironment.require("JDBC_USER"),
            ScenarioEnvironment.require("JDBC_PASSWORD"))) {
      switch (operation) {
        case "statement":
          statement(connection);
          break;
        case "prepared_statement":
          preparedStatement(connection);
          break;
        case "batch":
          batch(connection);
          break;
        case "stored_procedure":
          storedProcedure(connection);
          break;
        default:
          throw new IllegalArgumentException("unknown JDBC operation: " + operation);
      }
    }
  }

  private static void statement(Connection connection) throws SQLException {
    try (Statement statement = connection.createStatement();
        ResultSet result =
            statement.executeQuery(
                ScenarioEnvironment.getOrDefault(
                    "JDBC_STATEMENT_QUERY", "SELECT count(*) >= 0 FROM conformance.items"))) {
      requireSingleBoolean(result, true);
    }
  }

  private static void preparedStatement(Connection connection) throws SQLException {
    try (PreparedStatement statement =
        connection.prepareStatement("SELECT name FROM conformance.items WHERE id = ?")) {
      statement.setInt(1, -1);
      try (ResultSet result = statement.executeQuery()) {
        if (result.next()) {
          throw new IllegalStateException("prepared statement returned an unexpected row");
        }
      }
    }
  }

  private static void batch(Connection connection) throws SQLException {
    try (Statement statement = connection.createStatement()) {
      statement.addBatch("INSERT INTO conformance.items (id, name) VALUES (1, 'first')");
      statement.addBatch("INSERT INTO conformance.items (id, name) VALUES (2, 'second')");
      int[] updates = statement.executeBatch();
      if (updates.length != 2
          || Arrays.stream(updates).anyMatch(count -> count == Statement.EXECUTE_FAILED)) {
        throw new IllegalStateException(
            "expected two successful batch operations, got " + Arrays.toString(updates));
      }
    }
  }

  private static void storedProcedure(Connection connection) throws SQLException {
    try (CallableStatement statement =
        connection.prepareCall(
            ScenarioEnvironment.getOrDefault(
                "JDBC_STORED_PROCEDURE_CALL", "CALL conformance.noop()"))) {
      if (statement.execute()) {
        throw new IllegalStateException("stored procedure returned an unexpected result");
      }
    }
  }

  private static void requireSingleBoolean(ResultSet result, boolean expected) throws SQLException {
    if (!result.next() || result.getBoolean(1) != expected || result.next()) {
      throw new IllegalStateException("JDBC operation returned an unexpected result");
    }
  }
}
