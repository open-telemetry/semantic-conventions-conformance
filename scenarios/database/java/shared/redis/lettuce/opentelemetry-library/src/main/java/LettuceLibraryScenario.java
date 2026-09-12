/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.resource.ClientResources;
import io.opentelemetry.conformance.database.redis.LettuceScenario;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.lettuce.v5_1.LettuceTelemetry;

public final class LettuceLibraryScenario {
  private LettuceLibraryScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Lettuce operation argument");
    }
    RedisURI uri =
        RedisURI.Builder.redis(
                ScenarioEnvironment.require("DATABASE_HOST"),
                Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT")))
            .withDatabase(0)
            .build();
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ClientResources resources =
          ClientResources.builder()
              .tracing(LettuceTelemetry.create(sdk.openTelemetry()).createTracing())
              .build();
      try (RedisClient client = RedisClient.create(resources, uri)) {
        LettuceScenario.run(client, args[0]);
      } finally {
        resources.shutdown().get();
      }
    }
  }
}
