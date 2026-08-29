/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.r2dbc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.r2dbc.spi.ConnectionFactoryOptions;
import org.junit.jupiter.api.Test;

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
}
