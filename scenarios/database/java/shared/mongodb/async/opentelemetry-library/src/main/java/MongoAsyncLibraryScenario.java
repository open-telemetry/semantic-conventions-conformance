/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import com.mongodb.event.CommandListener;
import io.opentelemetry.conformance.database.mongodb.async.MongoAsyncScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.mongo.v3_1.MongoTelemetry;

public final class MongoAsyncLibraryScenario {
  private MongoAsyncLibraryScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one MongoDB operation argument");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      CommandListener commandListener =
          MongoTelemetry.create(sdk.openTelemetry()).createCommandListener();
      MongoAsyncScenario.run(args[0], commandListener);
    }
  }
}
