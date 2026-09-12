/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import com.mongodb.event.CommandListener;
import io.opentelemetry.conformance.database.mongodb.reactive.MongoReactiveScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.mongo.v3_1.MongoTelemetry;

public final class MongoReactiveLibraryScenario {
  private MongoReactiveLibraryScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one MongoDB operation argument");
    }
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      CommandListener commandListener =
          MongoTelemetry.create(sdk.openTelemetry()).createCommandListener();
      MongoReactiveScenario.run(args[0], commandListener);
    }
  }
}
