/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.r2dbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.r2dbc.spi.Connection;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import io.r2dbc.spi.R2dbcNonTransientResourceException;
import io.r2dbc.spi.Result;
import io.r2dbc.spi.Statement;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

class R2dbcScenarioTest {
  @Test
  void buildsPostgresqlConnectionOptions() {
    ConnectionFactoryOptions options =
        R2dbcScenario.connectionFactoryOptions(
            "r2dbc:postgresql://db.example:5433/conformance", "user", "secret");

    assertEquals("postgresql", options.getValue(ConnectionFactoryOptions.DRIVER));
    assertEquals("db.example", options.getValue(ConnectionFactoryOptions.HOST));
    assertEquals(5433, options.getValue(ConnectionFactoryOptions.PORT));
    assertEquals("conformance", options.getValue(ConnectionFactoryOptions.DATABASE));
    assertEquals("user", options.getValue(ConnectionFactoryOptions.USER));
    assertEquals("secret", options.getValue(ConnectionFactoryOptions.PASSWORD));
  }

  @Test
  void rejectsUnknownOperationBeforeCreatingAConnection() {
    IllegalArgumentException error =
        assertThrows(
            IllegalArgumentException.class, () -> R2dbcScenario.run(null, "unsupported-operation"));

    assertEquals("unknown R2DBC operation: unsupported-operation", error.getMessage());
  }

  @Test
  void consumesStoredProcedureResultBeforeClosingConnection() {
    AtomicBoolean resultConsumed = new AtomicBoolean();
    AtomicBoolean connectionClosed = new AtomicBoolean();

    Result result =
        proxy(
            Result.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("getRowsUpdated")) {
                return Mono.fromSupplier(
                    () -> {
                      resultConsumed.set(true);
                      return 0L;
                    });
              }
              throw new AssertionError("unexpected Result method: " + method.getName());
            });
    Statement statement =
        proxy(
            Statement.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("execute")) {
                return Flux.just(result);
              }
              throw new AssertionError("unexpected Statement method: " + method.getName());
            });
    Connection connection =
        proxy(
            Connection.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("createStatement")) {
                assertEquals("CALL conformance.noop()", arguments[0]);
                return statement;
              }
              if (method.getName().equals("close")) {
                return Mono.fromRunnable(
                    () -> {
                      assertTrue(resultConsumed.get(), "result was not consumed before close");
                      connectionClosed.set(true);
                    });
              }
              throw new AssertionError("unexpected Connection method: " + method.getName());
            });
    ConnectionFactory connectionFactory =
        proxy(
            ConnectionFactory.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("create")) {
                return Mono.just(connection);
              }
              throw new AssertionError("unexpected ConnectionFactory method: " + method.getName());
            });

    R2dbcScenario.run(connectionFactory, "stored_procedure");

    assertTrue(resultConsumed.get());
    assertTrue(connectionClosed.get());
  }

  @ParameterizedTest
  @ValueSource(booleans = {false, true})
  void handlesMissingTableErrorAndClosesConnection(boolean failWhileConsumingResult) {
    AtomicBoolean connectionClosed = new AtomicBoolean();
    ConnectionFactory connectionFactory =
        failingConnectionFactory(
            new R2dbcNonTransientResourceException("missing table", "42P01"),
            failWhileConsumingResult,
            connectionClosed);

    R2dbcScenario.run(connectionFactory, "error");

    assertTrue(connectionClosed.get(), "connection close did not complete");
  }

  @ParameterizedTest
  @ValueSource(booleans = {false, true})
  void propagatesDifferentSqlStateAndClosesConnection(boolean failWhileConsumingResult) {
    AtomicBoolean connectionClosed = new AtomicBoolean();
    R2dbcNonTransientResourceException failure =
        new R2dbcNonTransientResourceException("syntax error", "42601");
    ConnectionFactory connectionFactory =
        failingConnectionFactory(failure, failWhileConsumingResult, connectionClosed);

    assertSame(
        failure,
        assertThrows(
            R2dbcNonTransientResourceException.class,
            () -> R2dbcScenario.run(connectionFactory, "error")));
    assertTrue(connectionClosed.get(), "connection close did not complete");
  }

  @ParameterizedTest
  @ValueSource(booleans = {false, true})
  void propagatesNullSqlStateAndClosesConnection(boolean failWhileConsumingResult) {
    AtomicBoolean connectionClosed = new AtomicBoolean();
    R2dbcNonTransientResourceException failure =
        new R2dbcNonTransientResourceException("unknown SQL state", null, 0);
    ConnectionFactory connectionFactory =
        failingConnectionFactory(failure, failWhileConsumingResult, connectionClosed);

    assertSame(
        failure,
        assertThrows(
            R2dbcNonTransientResourceException.class,
            () -> R2dbcScenario.run(connectionFactory, "error")));
    assertTrue(connectionClosed.get(), "connection close did not complete");
  }

  @ParameterizedTest
  @ValueSource(booleans = {false, true})
  void propagatesNonR2dbcFailureAndClosesConnection(boolean failWhileConsumingResult) {
    AtomicBoolean connectionClosed = new AtomicBoolean();
    IllegalArgumentException failure = new IllegalArgumentException("unexpected failure");
    ConnectionFactory connectionFactory =
        failingConnectionFactory(failure, failWhileConsumingResult, connectionClosed);

    assertSame(
        failure,
        assertThrows(
            IllegalArgumentException.class, () -> R2dbcScenario.run(connectionFactory, "error")));
    assertTrue(connectionClosed.get(), "connection close did not complete");
  }

  @Test
  void rejectsUnexpectedQuerySuccessAndClosesConnection() {
    AtomicBoolean connectionClosed = new AtomicBoolean();
    ConnectionFactory connectionFactory =
        errorConnectionFactory(Flux.just(result(Mono.just(0L))), connectionClosed);

    IllegalStateException failure =
        assertThrows(
            IllegalStateException.class, () -> R2dbcScenario.run(connectionFactory, "error"));

    assertEquals("invalid statement unexpectedly succeeded", failure.getMessage());
    assertTrue(connectionClosed.get(), "connection close did not complete");
  }

  private static ConnectionFactory failingConnectionFactory(
      RuntimeException failure, boolean failWhileConsumingResult, AtomicBoolean connectionClosed) {
    return errorConnectionFactory(
        failWhileConsumingResult ? Flux.just(result(Mono.error(failure))) : Flux.error(failure),
        connectionClosed);
  }

  private static Result result(Mono<Long> rowsUpdated) {
    return proxy(
        Result.class,
        (ignored, method, arguments) -> {
          if (method.getName().equals("getRowsUpdated")) {
            return rowsUpdated;
          }
          throw new AssertionError("unexpected Result method: " + method.getName());
        });
  }

  private static ConnectionFactory errorConnectionFactory(
      Flux<Result> results, AtomicBoolean connectionClosed) {
    Statement statement =
        proxy(
            Statement.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("execute")) {
                return results;
              }
              throw new AssertionError("unexpected Statement method: " + method.getName());
            });
    Connection connection =
        proxy(
            Connection.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("createStatement")) {
                assertEquals("SELECT * FROM conformance.missing_items", arguments[0]);
                return statement;
              }
              if (method.getName().equals("close")) {
                return Mono.<Void>empty().doOnSuccess(unused -> connectionClosed.set(true));
              }
              throw new AssertionError("unexpected Connection method: " + method.getName());
            });
    return proxy(
        ConnectionFactory.class,
        (ignored, method, arguments) -> {
          if (method.getName().equals("create")) {
            return Mono.just(connection);
          }
          throw new AssertionError("unexpected ConnectionFactory method: " + method.getName());
        });
  }

  private static <T> T proxy(Class<T> type, InvocationHandler invocationHandler) {
    return type.cast(
        Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, invocationHandler));
  }
}
