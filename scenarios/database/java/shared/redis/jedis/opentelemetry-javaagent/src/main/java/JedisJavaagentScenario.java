/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import redis.clients.jedis.ClientSetInfoConfig;
import redis.clients.jedis.DefaultJedisClientConfig;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.Pipeline;
import redis.clients.jedis.Response;
import redis.clients.jedis.exceptions.JedisDataException;

public final class JedisJavaagentScenario {
  private JedisJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Jedis operation argument");
    }
    int database = Integer.parseInt(ScenarioEnvironment.require("DATABASE_NAME"));
    if (database < 0) {
      throw new IllegalArgumentException(
          "DATABASE_NAME must be a non-negative Redis database index");
    }
    String user = ScenarioEnvironment.require("DATABASE_USER");
    String password = ScenarioEnvironment.requirePresent("DATABASE_PASSWORD");
    // Skip HELLO and CLIENT SETINFO to keep startup spans out of the contract.
    DefaultJedisClientConfig.Builder config =
        DefaultJedisClientConfig.builder()
            .database(database)
            .autoNegotiateProtocol(false)
            .clientSetInfoConfig(ClientSetInfoConfig.DISABLED);
    if (!password.isEmpty()) {
      config.user(user).password(password);
    }
    try (Jedis jedis =
        new Jedis(
            ScenarioEnvironment.require("DATABASE_HOST"),
            Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT")),
            config.build())) {
      switch (args[0]) {
        case "set_get":
          requireOk(jedis.set("conformance:value", "value"));
          requireValue(jedis.get("conformance:value"), "value");
          break;
        case "pipeline":
          pipeline(jedis);
          break;
        case "error":
          error(jedis);
          break;
        default:
          throw new IllegalArgumentException("unknown Jedis operation: " + args[0]);
      }
    }
  }

  private static void pipeline(Jedis jedis) {
    try (Pipeline pipeline = jedis.pipelined()) {
      Response<String> first = pipeline.set("conformance:pipeline:1", "first");
      Response<String> second = pipeline.set("conformance:pipeline:2", "second");
      pipeline.sync();
      requireOk(first.get());
      requireOk(second.get());
    }
    requireValue(jedis.get("conformance:pipeline:1"), "first");
    requireValue(jedis.get("conformance:pipeline:2"), "second");
  }

  private static void error(Jedis jedis) {
    String key = "conformance:error";
    requireOk(jedis.set(key, "not-a-list"));
    try {
      jedis.lpush(key, "value");
      throw new IllegalStateException("LPUSH unexpectedly accepted a string key");
    } catch (JedisDataException expected) {
      if (!expected.getMessage().contains("WRONGTYPE")) {
        throw expected;
      }
    }
  }

  private static void requireOk(String response) {
    requireValue(response, "OK");
  }

  private static void requireValue(String actual, String expected) {
    if (!expected.equals(actual)) {
      throw new IllegalStateException("expected " + expected + ", got " + actual);
    }
  }
}
