/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import org.redisson.Redisson;
import org.redisson.api.RBatch;
import org.redisson.api.RBucket;
import org.redisson.api.RFuture;
import org.redisson.api.RList;
import org.redisson.api.RedissonClient;
import org.redisson.client.RedisException;
import org.redisson.config.Config;

public final class RedissonJavaagentScenario {
  private RedissonJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Redisson operation argument");
    }
    Config config = new Config();
    config
        .useSingleServer()
        .setAddress(
            "redis://"
                + ScenarioEnvironment.require("DATABASE_HOST")
                + ":"
                + ScenarioEnvironment.require("DATABASE_PORT"))
        .setDatabase(0)
        .setConnectionMinimumIdleSize(1)
        .setConnectionPoolSize(2)
        .setSubscriptionConnectionMinimumIdleSize(0)
        .setSubscriptionConnectionPoolSize(1);
    RedissonClient client = Redisson.create(config);
    try {
      switch (args[0]) {
        case "set_get":
          setGet(client);
          break;
        case "batch":
          batch(client);
          break;
        case "error":
          error(client);
          break;
        default:
          throw new IllegalArgumentException("unknown Redisson operation: " + args[0]);
      }
    } finally {
      client.shutdown();
    }
  }

  private static void setGet(RedissonClient client) {
    RBucket<String> bucket = client.getBucket("conformance:redisson:value");
    bucket.set("value");
    requireValue(bucket.get(), "value");
  }

  private static void batch(RedissonClient client) {
    RBatch batch = client.createBatch();
    RFuture<Void> first = batch.getBucket("conformance:redisson:batch:1").setAsync("first");
    RFuture<Void> second = batch.getBucket("conformance:redisson:batch:2").setAsync("second");
    batch.execute();
    first.toCompletableFuture().join();
    second.toCompletableFuture().join();
  }

  private static void error(RedissonClient client) {
    String key = "conformance:redisson:error";
    RList<String> list = client.getList(key);
    list.clear();
    list.add("value");
    try {
      client.getBucket(key).get();
      throw new IllegalStateException("GET unexpectedly accepted a list key");
    } catch (RedisException expected) {
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
