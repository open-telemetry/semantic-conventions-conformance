/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.mongodb.reactive.MongoReactiveScenario;

public final class MongoReactiveJavaagentScenario {
  private MongoReactiveJavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one MongoDB operation argument");
    }
    MongoReactiveScenario.run(args[0]);
  }
}
