/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.jdbc.JdbcScenario;

public final class JdbcJavaagentScenario {
  private JdbcJavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one JDBC operation argument");
    }
    JdbcScenario.run(args[0]);
  }
}
