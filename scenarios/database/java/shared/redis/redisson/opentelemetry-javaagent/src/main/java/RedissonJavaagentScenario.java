/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import org.redisson.Redisson;
import org.redisson.api.RBatch;
import org.redisson.api.RBucket;
import org.redisson.api.RDeque;
import org.redisson.api.RFuture;
import org.redisson.api.RedissonClient;
import org.redisson.client.RedisException;
import org.redisson.client.codec.StringCodec;
import org.redisson.config.Config;
import org.redisson.config.SingleServerConfig;

public final class RedissonJavaagentScenario {
  private RedissonJavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Redisson operation argument");
    }
    Config config = new Config();
    config.setCodec(StringCodec.INSTANCE);
    SingleServerConfig server =
        config
            .useSingleServer()
            .setAddress(
                "redis://"
                    + ScenarioEnvironment.require("DATABASE_HOST")
                    + ":"
                    + ScenarioEnvironment.require("DATABASE_PORT"))
            .setDatabase(Integer.parseInt(ScenarioEnvironment.require("DATABASE_NAME")))
            .setConnectionMinimumIdleSize(1)
            .setConnectionPoolSize(2)
            .setSubscriptionConnectionMinimumIdleSize(0)
            .setSubscriptionConnectionPoolSize(1);
    String user = ScenarioEnvironment.require("DATABASE_USER");
    String password = ScenarioEnvironment.requirePresent("DATABASE_PASSWORD");
    if (!password.isEmpty()) {
      server.setUsername(user).setPassword(password);
    }
    RedissonClient client = Redisson.create(config);
    try {
      switch (args[0]) {
        case "set_get":
          setGet(client);
          break;
        case "pipeline":
          pipeline(client);
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
    RBucket<String> bucket = client.getBucket("conformance:value");
    bucket.set("value");
    requireValue(bucket.get(), "value");
  }

  private static void pipeline(RedissonClient client) {
    RBatch batch = client.createBatch();
    RFuture<Void> first = batch.getBucket("conformance:pipeline:1").setAsync("first");
    RFuture<Void> second = batch.getBucket("conformance:pipeline:2").setAsync("second");
    batch.execute();
    first.toCompletableFuture().join();
    second.toCompletableFuture().join();
    requireValue(client.<String>getBucket("conformance:pipeline:1").get(), "first");
    requireValue(client.<String>getBucket("conformance:pipeline:2").get(), "second");
  }

  private static void error(RedissonClient client) {
    String key = "conformance:error";
    client.getBucket(key).set("not-a-list");
    RDeque<String> deque = client.getDeque(key);
    try {
      deque.addFirst("value");
      throw new IllegalStateException("LPUSH unexpectedly accepted a string key");
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
