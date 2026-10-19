/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.jdbc;

import io.opentelemetry.conformance.database.sql.SqlContract;
import io.opentelemetry.conformance.database.sql.SqlContract.Batch;
import io.opentelemetry.conformance.database.sql.SqlContract.Operation;
import io.opentelemetry.conformance.database.sql.SqlContract.Parameter;
import io.opentelemetry.conformance.database.sql.SqlContract.PreparedQuery;
import io.opentelemetry.conformance.database.sql.SqlContract.Query;
import io.opentelemetry.conformance.database.sql.SqlContract.StoredProcedure;
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

  public static void run() throws SQLException {
    Operation operation = SqlContract.selectedScenario();
    try (Connection connection =
        DriverManager.getConnection(
            ScenarioEnvironment.require("JDBC_URL"),
            ScenarioEnvironment.require("JDBC_USER"),
            ScenarioEnvironment.require("JDBC_PASSWORD"))) {
      run(connection, operation);
    }
  }

  static void run(Connection connection, Operation operation) throws SQLException {
    switch (operation) {
      case Query query -> statement(connection, query);
      case PreparedQuery query -> preparedStatement(connection, query);
      case Batch batch -> batch(connection, batch);
      case StoredProcedure procedure -> storedProcedure(connection, procedure);
    }
  }

  private static void statement(Connection connection, Query operation) throws SQLException {
    try (Statement statement = connection.createStatement();
        ResultSet result = statement.executeQuery(operation.sql())) {
      consume(result);
    }
  }

  private static void preparedStatement(Connection connection, PreparedQuery operation)
      throws SQLException {
    try (PreparedStatement statement =
        connection.prepareStatement(operation.renderSql(index -> "?"))) {
      int index = 1;
      for (Parameter parameter : operation.parameters()) {
        statement.setInt(index++, parameter.integer());
      }
      try (ResultSet result = statement.executeQuery()) {
        consume(result);
      }
    }
  }

  private static void batch(Connection connection, Batch operation) throws SQLException {
    try (Statement statement = connection.createStatement()) {
      for (String sql : operation.statements()) {
        statement.addBatch(sql);
      }
      int[] updates = statement.executeBatch();
      if (updates.length != operation.statements().size()
          || Arrays.stream(updates).anyMatch(count -> count == Statement.EXECUTE_FAILED)) {
        throw new IllegalStateException(
            "expected "
                + operation.statements().size()
                + " successful batch operations, got "
                + Arrays.toString(updates));
      }
    }
  }

  private static void storedProcedure(Connection connection, StoredProcedure operation)
      throws SQLException {
    try (CallableStatement statement = connection.prepareCall(operation.sql())) {
      boolean hasResultSet = statement.execute();
      while (true) {
        if (hasResultSet) {
          try (ResultSet result = statement.getResultSet()) {
            consume(result);
          }
        } else if (statement.getUpdateCount() == -1) {
          break;
        }
        hasResultSet = statement.getMoreResults();
      }
    }
  }

  private static void consume(ResultSet result) throws SQLException {
    while (result.next()) {
      // Fetch every row so deferred driver errors surface.
    }
  }
}
