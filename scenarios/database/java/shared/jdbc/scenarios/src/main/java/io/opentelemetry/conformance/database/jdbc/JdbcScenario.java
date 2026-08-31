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

  public static void run(String scenario) throws SQLException {
    Operation workload =
        SqlContract.workload(ScenarioEnvironment.require("DATABASE_BACKEND")).scenario(scenario);
    try (Connection connection =
        DriverManager.getConnection(
            ScenarioEnvironment.require("JDBC_URL"),
            ScenarioEnvironment.require("JDBC_USER"),
            ScenarioEnvironment.require("JDBC_PASSWORD"))) {
      switch (workload) {
        case Query query -> statement(connection, query);
        case PreparedQuery query -> preparedStatement(connection, query);
        case Batch batch -> batch(connection, batch);
        case StoredProcedure procedure -> storedProcedure(connection, procedure);
      }
    }
  }

  private static void statement(Connection connection, Query operation) throws SQLException {
    try (Statement statement = connection.createStatement();
        ResultSet result = statement.executeQuery(operation.sql())) {
      requireSingleBoolean(result, operation.expected());
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
        int rows = 0;
        while (result.next()) {
          rows++;
        }
        if (rows != operation.expectedRows()) {
          throw new IllegalStateException(
              "expected " + operation.expectedRows() + " rows, got " + rows);
        }
      }
    }
  }

  private static void batch(Connection connection, Batch operation) throws SQLException {
    try (Statement statement = connection.createStatement()) {
      for (String sql : operation.statements()) {
        statement.addBatch(sql);
      }
      int[] updates = statement.executeBatch();
      if (updates.length != operation.expectedSuccessfulStatements()
          || Arrays.stream(updates).anyMatch(count -> count == Statement.EXECUTE_FAILED)) {
        throw new IllegalStateException(
            "expected "
                + operation.expectedSuccessfulStatements()
                + " successful batch operations, got "
                + Arrays.toString(updates));
      }
    }
  }

  private static void storedProcedure(Connection connection, StoredProcedure operation)
      throws SQLException {
    try (CallableStatement statement =
        connection.prepareCall("CALL " + operation.procedure() + "()")) {
      int resultSets = resultSetCount(statement);
      if (resultSets != operation.expectedResultSets()) {
        throw new IllegalStateException(
            "expected "
                + operation.expectedResultSets()
                + " stored procedure result sets, got "
                + resultSets);
      }
    }
  }

  private static int resultSetCount(CallableStatement statement) throws SQLException {
    int resultSets = 0;
    boolean hasResultSet = statement.execute();
    while (hasResultSet || statement.getUpdateCount() != -1) {
      if (hasResultSet) {
        resultSets++;
      }
      hasResultSet = statement.getMoreResults();
    }
    return resultSets;
  }

  private static void requireSingleBoolean(ResultSet result, boolean expected) throws SQLException {
    if (!result.next() || result.getBoolean(1) != expected || result.next()) {
      throw new IllegalStateException("JDBC operation returned an unexpected result");
    }
  }
}
