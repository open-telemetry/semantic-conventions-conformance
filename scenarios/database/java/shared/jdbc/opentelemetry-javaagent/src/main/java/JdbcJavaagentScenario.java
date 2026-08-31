/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.jdbc.JdbcScenario;

public final class JdbcJavaagentScenario {
  private JdbcJavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 0) {
      throw new IllegalArgumentException("expected no JDBC operation arguments");
    }
    JdbcScenario.run();
  }
}
