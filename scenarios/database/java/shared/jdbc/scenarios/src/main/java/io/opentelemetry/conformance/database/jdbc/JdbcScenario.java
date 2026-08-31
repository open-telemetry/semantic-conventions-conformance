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

/** Exercises individual JDBC execution paths against a relational database. */
public final class JdbcScenario {
  private JdbcScenario() {}

  public static void run() throws SQLException {
    String value = ScenarioEnvironment.require("OTEL_CONFORMANCE_SCENARIO_INDEX");
    int scenario;
    try {
      scenario = Integer.parseInt(value);
    } catch (NumberFormatException error) {
      throw new IllegalArgumentException(
          "OTEL_CONFORMANCE_SCENARIO_INDEX must be a decimal integer: " + value, error);
    }
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
        ResultSet result = statement.executeQuery(operation.sql())) {}
  }

  private static void preparedStatement(Connection connection, PreparedQuery operation)
      throws SQLException {
    try (PreparedStatement statement =
        connection.prepareStatement(operation.renderSql(index -> "?"))) {
      int index = 1;
      for (Parameter parameter : operation.parameters()) {
        statement.setInt(index++, parameter.integer());
      }
      try (ResultSet result = statement.executeQuery()) {}
    }
  }

  private static void batch(Connection connection, Batch operation) throws SQLException {
    try (Statement statement = connection.createStatement()) {
      for (String sql : operation.statements()) {
        statement.addBatch(sql);
      }
      statement.executeBatch();
    }
  }

  private static void storedProcedure(Connection connection, StoredProcedure operation)
      throws SQLException {
    try (CallableStatement statement =
        connection.prepareCall("CALL " + operation.procedure() + "()")) {
      statement.execute();
    }
  }
}
