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
    RedisURI.Builder uri =
        RedisURI.Builder.redis(
                ScenarioEnvironment.require("DATABASE_HOST"),
                Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT")))
            .withDatabase(Integer.parseInt(ScenarioEnvironment.require("DATABASE_NAME")));
    String user = ScenarioEnvironment.require("DATABASE_USER");
    String password = ScenarioEnvironment.requirePresent("DATABASE_PASSWORD");
    if (!password.isEmpty()) {
      uri.withAuthentication(user, password);
    }
    try (RedisClient client = RedisClient.create(uri.build())) {
      LettuceScenario.run(client, args[0]);
    }
  }
}
