/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.redis;

import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisCommandExecutionException;
import io.lettuce.core.RedisFuture;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.async.RedisAsyncCommands;
import java.util.concurrent.TimeUnit;

/** Exercises synchronous, pipelined, and failed Lettuce commands. */
public final class LettuceScenario {
  private LettuceScenario() {}

  public static void run(RedisClient client, String operation) throws Exception {
    try (StatefulRedisConnection<String, String> connection = client.connect()) {
      switch (operation) {
        case "set_get":
          requireValue(connection.sync().set("conformance:lettuce:value", "value"), "OK");
          requireValue(connection.sync().get("conformance:lettuce:value"), "value");
          break;
        case "pipeline":
          pipeline(connection);
          break;
        case "error":
          error(connection);
          break;
        default:
          throw new IllegalArgumentException("unknown Lettuce operation: " + operation);
      }
    }
  }

  private static void pipeline(StatefulRedisConnection<String, String> connection)
      throws Exception {
    connection.setAutoFlushCommands(false);
    RedisAsyncCommands<String, String> commands = connection.async();
    RedisFuture<String> first = commands.set("conformance:lettuce:pipeline:1", "first");
    RedisFuture<String> second = commands.set("conformance:lettuce:pipeline:2", "second");
    connection.flushCommands();
    requireValue(first.get(5, TimeUnit.SECONDS), "OK");
    requireValue(second.get(5, TimeUnit.SECONDS), "OK");
    connection.setAutoFlushCommands(true);
  }

  private static void error(StatefulRedisConnection<String, String> connection) {
    String key = "conformance:lettuce:error";
    requireValue(connection.sync().set(key, "not-a-list"), "OK");
    try {
      connection.sync().lpush(key, "value");
      throw new IllegalStateException("LPUSH unexpectedly accepted a string key");
    } catch (RedisCommandExecutionException expected) {
      if (!expected.getMessage().contains("WRONGTYPE")) {
        throw expected;
      }
    }
  }

  private static void requireValue(String actual, String expected) {
    if (!expected.equals(actual)) {
      throw new IllegalStateException("expected " + expected + ", got " + actual);
    }
  }
}
