/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.mongodb.sync.MongoSyncScenario;

public final class MongoSyncJavaagentScenario {
  private MongoSyncJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one MongoDB operation argument");
    }
    MongoSyncScenario.run(args[0]);
  }
}
