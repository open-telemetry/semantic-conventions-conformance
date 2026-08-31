/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.r2dbc;

import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import io.r2dbc.spi.Batch;
import io.r2dbc.spi.Connection;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import io.r2dbc.spi.R2dbcException;
import io.r2dbc.spi.Result;
import java.time.Duration;
import java.util.Objects;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

/** Exercises individual reactive R2DBC execution paths against PostgreSQL. */
public final class R2dbcScenario {
  private static final Duration TIMEOUT = Duration.ofSeconds(30);

  private R2dbcScenario() {}

  public static ConnectionFactoryOptions connectionFactoryOptions() {
    return connectionFactoryOptions(
        ScenarioEnvironment.require("R2DBC_URL"),
        ScenarioEnvironment.require("R2DBC_USER"),
        ScenarioEnvironment.require("R2DBC_PASSWORD"));
  }

  static ConnectionFactoryOptions connectionFactoryOptions(
      String url, String user, String password) {
    return ConnectionFactoryOptions.parse(url)
        .mutate()
        .option(ConnectionFactoryOptions.USER, user)
        .option(ConnectionFactoryOptions.PASSWORD, password)
        .build();
  }

  public static void run(ConnectionFactory connectionFactory, String operation) {
    Operation parsedOperation = Operation.parse(operation);
    Mono.usingWhen(
            Mono.from(connectionFactory.create()),
            connection -> execute(connection, parsedOperation),
            connection -> Mono.from(connection.close()))
        .block(TIMEOUT);
  }

  private static Mono<Void> execute(Connection connection, Operation operation) {
    switch (operation) {
      case STATEMENT:
        return statement(connection);
      case BIND:
        return bind(connection);
      case BATCH:
        return batch(connection);
      case ERROR:
        return error(connection);
    }
    throw new AssertionError("unhandled R2DBC operation: " + operation);
  }

  private static Mono<Void> statement(Connection connection) {
    return Mono.from(
            connection.createStatement("SELECT count(*) >= 0 FROM conformance.items").execute())
        .flatMap(result -> Mono.from(result.map((row, metadata) -> row.get(0, Boolean.class))))
        .filter(Boolean.TRUE::equals)
        .switchIfEmpty(
            Mono.error(new IllegalStateException("statement returned an unexpected result")))
        .then();
  }

  private static Mono<Void> bind(Connection connection) {
    return Mono.from(
            connection
                .createStatement("SELECT name FROM conformance.items WHERE id = $1")
                .bind(0, -1)
                .execute())
        .flatMapMany(result -> result.map((row, metadata) -> row.get(0, String.class)))
        .hasElements()
        .flatMap(
            hasRows ->
                hasRows
                    ? Mono.error(new IllegalStateException("bind returned an unexpected row"))
                    : Mono.empty());
  }

  private static Mono<Void> batch(Connection connection) {
    Batch batch =
        connection
            .createBatch()
            .add("INSERT INTO conformance.items (id, name) VALUES (1001, 'first')")
            .add("INSERT INTO conformance.items (id, name) VALUES (1002, 'second')");
    return Flux.from(batch.execute())
        .flatMap(Result::getRowsUpdated)
        .reduce(0L, Long::sum)
        .filter(updated -> updated == 2)
        .switchIfEmpty(Mono.error(new IllegalStateException("batch did not insert two rows")))
        .then();
  }

  private static Mono<Void> error(Connection connection) {
    return Flux.from(
            connection.createStatement("SELECT * FROM conformance.missing_items").execute())
        .flatMap(Result::getRowsUpdated)
        .then(
            Mono.<Void>error(new IllegalStateException("invalid statement unexpectedly succeeded")))
        .onErrorResume(
            R2dbcException.class,
            error ->
                Objects.equals("42P01", error.getSqlState()) ? Mono.empty() : Mono.error(error));
  }

  private enum Operation {
    STATEMENT,
    BIND,
    BATCH,
    ERROR;

    private static Operation parse(String value) {
      try {
        return valueOf(value.toUpperCase(java.util.Locale.ROOT));
      } catch (IllegalArgumentException error) {
        throw new IllegalArgumentException("unknown R2DBC operation: " + value, error);
      }
    }
  }
}
