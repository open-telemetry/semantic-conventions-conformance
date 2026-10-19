/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.r2dbc.R2dbcScenario;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactoryOptions;

public final class R2dbcJavaagentScenario {
  private R2dbcJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one R2DBC operation argument");
    }
    ConnectionFactoryOptions options = R2dbcScenario.connectionFactoryOptions();
    R2dbcScenario.run(ConnectionFactories.get(options), args[0]);
  }
}
