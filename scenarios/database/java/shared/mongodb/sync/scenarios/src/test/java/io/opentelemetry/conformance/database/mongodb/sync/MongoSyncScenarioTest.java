/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.sync;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.mongodb.MongoQueryException;
import com.mongodb.ServerAddress;
import com.mongodb.client.FindIterable;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoDatabase;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.bson.BsonDocument;
import org.bson.Document;
import org.junit.jupiter.api.Test;

class MongoSyncScenarioTest {
  @Test
  void createsListenerWithConfiguredSeedsBeforeConnecting() {
    RuntimeException stopBeforeConnecting = new RuntimeException("listener factory invoked");

    RuntimeException thrown =
        assertThrows(
            RuntimeException.class,
            () ->
                MongoSyncScenario.run(
                    "find",
                    servers -> {
                      assertEquals(List.of(new ServerAddress("127.0.0.1", 43210)), servers);
                      throw stopBeforeConnecting;
                    }));

    assertSame(stopBeforeConnecting, thrown);
  }

  @Test
  void acceptsExpectedRejectedFindAndClosesClient() {
    AtomicBoolean closed = new AtomicBoolean();
    MongoQueryException failure =
        new MongoQueryException(
            BsonDocument.parse(
                "{\"ok\": 0, \"code\": 2, \"errmsg\": \"unknown operator: $invalid\"}"),
            new ServerAddress());

    MongoSyncScenario.run(client(null, failure, closed), "error");

    assertTrue(closed.get());
  }

  @Test
  void rejectsUnexpectedCommandSuccessAndClosesClient() {
    AtomicBoolean closed = new AtomicBoolean();

    IllegalStateException thrown =
        assertThrows(
            IllegalStateException.class,
            () -> MongoSyncScenario.run(client(new Document(), null, closed), "error"));

    assertEquals("MongoDB accepted an invalid find filter", thrown.getMessage());
    assertTrue(closed.get());
  }

  @Test
  void propagatesUnexpectedServerCode() {
    AtomicBoolean closed = new AtomicBoolean();
    MongoQueryException failure =
        new MongoQueryException(
            BsonDocument.parse(
                "{\"ok\": 0, \"code\": 13, \"errmsg\": \"unknown operator: $invalid\"}"),
            new ServerAddress());

    MongoQueryException thrown =
        assertThrows(
            MongoQueryException.class,
            () -> MongoSyncScenario.run(client(null, failure, closed), "error"));

    assertSame(failure, thrown);
    assertTrue(closed.get());
  }

  @Test
  void propagatesUnrelatedQueryFailureWithSameCode() {
    AtomicBoolean closed = new AtomicBoolean();
    MongoQueryException failure =
        new MongoQueryException(
            BsonDocument.parse("{\"ok\": 0, \"code\": 2, \"errmsg\": \"unrelated invalid query\"}"),
            new ServerAddress());

    MongoQueryException thrown =
        assertThrows(
            MongoQueryException.class,
            () -> MongoSyncScenario.run(client(null, failure, closed), "error"));

    assertSame(failure, thrown);
    assertTrue(closed.get());
  }

  @Test
  void propagatesUnrelatedClientFailure() {
    AtomicBoolean closed = new AtomicBoolean();
    IllegalStateException failure = new IllegalStateException("client failed");

    IllegalStateException thrown =
        assertThrows(
            IllegalStateException.class,
            () -> MongoSyncScenario.run(client(null, failure, closed), "error"));

    assertSame(failure, thrown);
    assertTrue(closed.get());
  }

  private static MongoClient client(
      Document result, RuntimeException failure, AtomicBoolean closed) {
    FindIterable<?> find =
        proxy(
            FindIterable.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("first")) {
                if (failure != null) {
                  throw failure;
                }
                return result;
              }
              throw new AssertionError("unexpected FindIterable method: " + method.getName());
            });
    MongoCollection<?> collection =
        proxy(
            MongoCollection.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("find")) {
                assertEquals(new Document("_id", new Document("$invalid", 1)), arguments[0]);
                return find;
              }
              throw new AssertionError("unexpected MongoCollection method: " + method.getName());
            });
    MongoDatabase database =
        proxy(
            MongoDatabase.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("getCollection")) {
                assertEquals("items", arguments[0]);
                return collection;
              }
              throw new AssertionError("unexpected MongoDatabase method: " + method.getName());
            });
    return proxy(
        MongoClient.class,
        (ignored, method, arguments) -> {
          if (method.getName().equals("getDatabase")) {
            assertEquals("conformance", arguments[0]);
            return database;
          }
          if (method.getName().equals("close")) {
            closed.set(true);
            return null;
          }
          throw new AssertionError("unexpected MongoClient method: " + method.getName());
        });
  }

  private static <T> T proxy(Class<T> type, InvocationHandler invocationHandler) {
    return type.cast(
        Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, invocationHandler));
  }
}
