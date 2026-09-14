/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.mongodb.async.MongoAsyncScenario;

public final class MongoAsyncJavaagentScenario {
  private MongoAsyncJavaagentScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one MongoDB operation argument");
    }
    MongoAsyncScenario.run(args[0]);
  }
}
