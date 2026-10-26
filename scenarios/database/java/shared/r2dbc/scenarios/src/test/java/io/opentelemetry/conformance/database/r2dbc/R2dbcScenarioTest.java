/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.r2dbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.r2dbc.spi.Connection;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import io.r2dbc.spi.Result;
import io.r2dbc.spi.Statement;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
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

  private static <T> T proxy(Class<T> type, InvocationHandler invocationHandler) {
    return type.cast(
        Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, invocationHandler));
  }
}
