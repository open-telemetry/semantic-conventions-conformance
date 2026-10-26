/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.opentelemetry.conformance.database.sql.SqlContract.Batch;
import io.opentelemetry.conformance.database.sql.SqlContract.Parameter;
import io.opentelemetry.conformance.database.sql.SqlContract.PreparedQuery;
import io.opentelemetry.conformance.database.sql.SqlContract.Query;
import io.opentelemetry.conformance.database.sql.SqlContract.StoredProcedure;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

class JdbcScenarioTest {
  @ParameterizedTest
  @ValueSource(ints = {0, 1, 3})
  void consumesDirectQueriesWithoutInspectingValues(int rowCount) throws SQLException {
    List<String> events = new ArrayList<>();
    ResultSet result = rows("query", rowCount, events);
    Statement statement =
        jdbc(
            Statement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "executeQuery" -> {
                    assertEquals("SELECT name FROM items", arguments[0]);
                    yield result;
                  }
                  case "close" -> events.add("statement.close");
                  default -> throw new AssertionError(method);
                });

    JdbcScenario.run(
        connection("createStatement", null, statement), new Query("SELECT name FROM items"));

    assertEquals(rowCount + 1, Collections.frequency(events, "query.next"));
    assertEquals(
        List.of("query.close", "statement.close"),
        events.subList(events.size() - 2, events.size()));
  }

  @Test
  void bindsPreparedParametersInOrderAndConsumesReturnedRows() throws SQLException {
    List<String> events = new ArrayList<>();
    List<List<Object>> bindings = new ArrayList<>();
    ResultSet result = rows("prepared", 2, events);
    PreparedStatement statement =
        jdbc(
            PreparedStatement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "setInt" -> {
                    events.add("prepared.bind");
                    bindings.add(List.of(arguments[0], arguments[1]));
                    yield null;
                  }
                  case "executeQuery" -> {
                    events.add("prepared.execute");
                    yield result;
                  }
                  case "close" -> events.add("statement.close");
                  default -> throw new AssertionError(method);
                });

    JdbcScenario.run(
        connection("prepareStatement", "SELECT ?, ?", statement),
        new PreparedQuery("SELECT ${1}, ${2}", List.of(new Parameter(7), new Parameter(-2))));

    assertEquals(List.of(List.of(1, 7), List.of(2, -2)), bindings);
    assertEquals(
        List.of(
            "prepared.bind",
            "prepared.bind",
            "prepared.execute",
            "prepared.next",
            "prepared.next",
            "prepared.next",
            "prepared.close",
            "statement.close"),
        events);
  }

  @ParameterizedTest
  @ValueSource(strings = {"CALL conformance.noop()", "CALL other_schema.record_value(7)"})
  void executesContractCallSqlAndConsumesAllProcedureResults(String sql) throws SQLException {
    List<String> events = new ArrayList<>();
    ResultSet first = rows("first", 2, events);
    ResultSet second = rows("second", 1, events);
    AtomicInteger resultIndex = new AtomicInteger();
    CallableStatement statement =
        jdbc(
            CallableStatement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "execute" -> {
                    events.add("execute");
                    yield true;
                  }
                  case "getResultSet" ->
                      switch (resultIndex.get()) {
                        case 0 -> first;
                        case 2 -> second;
                        default -> throw new AssertionError("unexpected result index");
                      };
                  case "getUpdateCount" -> {
                    events.add("updateCount");
                    yield resultIndex.get() == 1 ? 4 : -1;
                  }
                  case "getMoreResults" -> {
                    events.add("moreResults");
                    yield resultIndex.incrementAndGet() == 2;
                  }
                  case "close" -> events.add("statement.close");
                  default -> throw new AssertionError(method);
                });

    JdbcScenario.run(connection("prepareCall", sql, statement), new StoredProcedure(sql));

    assertEquals(
        List.of(
            "execute",
            "first.next",
            "first.next",
            "first.next",
            "first.close",
            "moreResults",
            "updateCount",
            "moreResults",
            "second.next",
            "second.next",
            "second.close",
            "moreResults",
            "updateCount",
            "statement.close"),
        events);
  }

  @ParameterizedTest
  @ValueSource(ints = {-1, 0, 7})
  void consumesProceduresWithoutResultSets(int updateCount) throws SQLException {
    List<String> events = new ArrayList<>();
    AtomicBoolean advanced = new AtomicBoolean();
    CallableStatement statement =
        jdbc(
            CallableStatement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "execute" -> false;
                  case "getUpdateCount" -> advanced.get() ? -1 : updateCount;
                  case "getMoreResults" -> {
                    events.add("moreResults");
                    advanced.set(true);
                    yield false;
                  }
                  case "close" -> events.add("statement.close");
                  default -> throw new AssertionError(method);
                });

    JdbcScenario.run(
        connection("prepareCall", "CALL conformance.noop()", statement),
        new StoredProcedure("CALL conformance.noop()"));

    assertEquals(
        updateCount == -1 ? List.of("statement.close") : List.of("moreResults", "statement.close"),
        events);
  }

  @ParameterizedTest
  @ValueSource(strings = {"executeQuery", "next"})
  void propagatesQueryExecutionAndFetchErrorsAndClosesResources(String failingMethod) {
    SQLException failure = new SQLException("driver failed");
    List<String> closed = new ArrayList<>();
    ResultSet result =
        jdbc(
            ResultSet.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "next" -> throw failure;
                  case "close" -> closed.add("result");
                  default -> throw new AssertionError(method);
                });
    Statement statement =
        jdbc(
            Statement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "executeQuery" -> {
                    if (failingMethod.equals("executeQuery")) {
                      throw failure;
                    }
                    yield result;
                  }
                  case "close" -> closed.add("statement");
                  default -> throw new AssertionError(method);
                });

    assertSame(
        failure,
        assertThrows(
            SQLException.class,
            () ->
                JdbcScenario.run(
                    connection("createStatement", null, statement), new Query("SELECT 1"))));
    assertEquals(
        failingMethod.equals("next") ? List.of("result", "statement") : List.of("statement"),
        closed);
  }

  @Test
  void propagatesErrorsAdvancingProcedureResultsAndClosesTheStatement() {
    SQLException failure = new SQLException("next result failed");
    List<String> closed = new ArrayList<>();
    CallableStatement statement =
        jdbc(
            CallableStatement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "execute" -> false;
                  case "getUpdateCount" -> 0;
                  case "getMoreResults" -> throw failure;
                  case "close" -> closed.add("statement");
                  default -> throw new AssertionError(method);
                });

    assertSame(
        failure,
        assertThrows(
            SQLException.class,
            () ->
                JdbcScenario.run(
                    connection("prepareCall", "CALL conformance.noop()", statement),
                    new StoredProcedure("CALL conformance.noop()"))));
    assertEquals(List.of("statement"), closed);
  }

  @Test
  void acceptsSuccessfulBatchResultsWithoutRequiringAffectedRows() throws SQLException {
    List<String> submitted = new ArrayList<>();
    List<String> closed = new ArrayList<>();

    JdbcScenario.run(
        batchConnection(new int[] {Statement.SUCCESS_NO_INFO, 0}, submitted, closed),
        new Batch(List.of("DELETE FROM items", "UPDATE items SET name = 'updated'")));

    assertEquals(List.of("DELETE FROM items", "UPDATE items SET name = 'updated'"), submitted);
    assertEquals(List.of("statement"), closed);
  }

  @ParameterizedTest
  @MethodSource("unsuccessfulBatchResults")
  void rejectsIncompleteOrFailedBatchResults(int[] updates) {
    List<String> submitted = new ArrayList<>();
    List<String> closed = new ArrayList<>();

    assertEquals(
        "expected 2 successful batch operations, got " + Arrays.toString(updates),
        assertThrows(
                IllegalStateException.class,
                () ->
                    JdbcScenario.run(
                        batchConnection(updates, submitted, closed),
                        new Batch(
                            List.of("DELETE FROM items", "UPDATE items SET name = 'updated'"))))
            .getMessage());
    assertEquals(List.of("statement"), closed);
  }

  private static Stream<int[]> unsuccessfulBatchResults() {
    return Stream.of(new int[] {1}, new int[] {1, Statement.EXECUTE_FAILED});
  }

  private static Connection batchConnection(
      int[] updates, List<String> submitted, List<String> closed) {
    Statement statement =
        jdbc(
            Statement.class,
            (proxy, method, arguments) ->
                switch (method.getName()) {
                  case "addBatch" -> submitted.add((String) arguments[0]);
                  case "executeBatch" -> updates;
                  case "close" -> closed.add("statement");
                  default -> throw new AssertionError(method);
                });
    return connection("createStatement", null, statement);
  }

  private static Connection connection(String methodName, String sql, Statement statement) {
    return jdbc(
        Connection.class,
        (proxy, method, arguments) -> {
          assertEquals(methodName, method.getName());
          if (sql == null) {
            assertNull(arguments);
          } else {
            assertEquals(1, arguments.length);
            assertEquals(sql, arguments[0]);
          }
          return statement;
        });
  }

  private static ResultSet rows(String name, int count, List<String> events) {
    AtomicInteger nextCalls = new AtomicInteger();
    return jdbc(
        ResultSet.class,
        (proxy, method, arguments) ->
            switch (method.getName()) {
              case "next" -> {
                events.add(name + ".next");
                yield nextCalls.getAndIncrement() < count;
              }
              case "close" -> events.add(name + ".close");
              default -> throw new AssertionError(method);
            });
  }

  private static <T> T jdbc(Class<T> type, InvocationHandler handler) {
    return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, handler));
  }
}
