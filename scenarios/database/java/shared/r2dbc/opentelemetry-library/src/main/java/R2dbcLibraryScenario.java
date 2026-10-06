/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.r2dbc.R2dbcScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.r2dbc.v1_0.R2dbcTelemetry;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;

public final class R2dbcLibraryScenario {
  private R2dbcLibraryScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one R2DBC operation argument");
    }
    ConnectionFactoryOptions options = R2dbcScenario.connectionFactoryOptions();
    ConnectionFactory connectionFactory = ConnectionFactories.get(options);
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ConnectionFactory instrumented =
          R2dbcTelemetry.create(sdk.openTelemetry())
              .wrapConnectionFactory(connectionFactory, options);
      R2dbcScenario.run(instrumented, args[0]);
    }
  }
}
