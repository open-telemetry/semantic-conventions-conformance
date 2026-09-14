/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.opentelemetry.conformance.database.redis.LettuceScenario;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;

public final class LettuceJavaagentScenario {
  private LettuceJavaagentScenario() {}

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
    try (RedisClient client = RedisClient.create(uri)) {
      LettuceScenario.run(client, args[0]);
    }
  }
}
