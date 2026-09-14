/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
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
    try (Jedis jedis =
        new Jedis(
            ScenarioEnvironment.require("DATABASE_HOST"),
            Integer.parseInt(ScenarioEnvironment.require("DATABASE_PORT")))) {
      switch (args[0]) {
        case "set_get":
          requireOk(jedis.set("conformance:jedis:value", "value"));
          requireValue(jedis.get("conformance:jedis:value"), "value");
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
      Response<String> first = pipeline.set("conformance:jedis:pipeline:1", "first");
      Response<String> second = pipeline.set("conformance:jedis:pipeline:2", "second");
      pipeline.sync();
      requireOk(first.get());
      requireOk(second.get());
    }
  }

  private static void error(Jedis jedis) {
    String key = "conformance:jedis:error";
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
