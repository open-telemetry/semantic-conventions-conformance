/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.reactive;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.mongodb.ServerAddress;
import com.mongodb.client.result.UpdateResult;
import com.mongodb.reactivestreams.client.MongoClient;
import com.mongodb.reactivestreams.client.MongoCollection;
import com.mongodb.reactivestreams.client.MongoDatabase;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

class MongoReactiveScenarioTest {
  @Test
  void createsListenerWithConfiguredSeedsBeforeConnecting() {
    RuntimeException stopBeforeConnecting = new RuntimeException("listener factory invoked");

    RuntimeException thrown =
        assertThrows(
            RuntimeException.class,
            () ->
                MongoReactiveScenario.run(
                    "find",
                    servers -> {
                      assertEquals(List.of(new ServerAddress("127.0.0.1", 43210)), servers);
                      throw stopBeforeConnecting;
                    }));

    assertSame(stopBeforeConnecting, thrown);
  }

  @Test
  void returnsLastValueAfterPublisherCompletes() throws Exception {
    Publisher<String> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onNext("first");
          subscriber.onNext("last");
          subscriber.onComplete();
        };

    assertEquals("last", MongoReactiveScenario.await(publisher, Duration.ofSeconds(1)));
  }

  @Test
  void returnsNullWhenPublisherCompletesEmpty() throws Exception {
    Publisher<String> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onComplete();
        };

    assertNull(MongoReactiveScenario.await(publisher, Duration.ofSeconds(1)));
  }

  @Test
  void propagatesPublisherFailureAfterAnItem() {
    IllegalStateException failure = new IllegalStateException("publisher failed");
    Publisher<String> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onNext("incomplete");
          subscriber.onError(failure);
        };

    ExecutionException thrown =
        assertThrows(
            ExecutionException.class,
            () -> MongoReactiveScenario.await(publisher, Duration.ofSeconds(1)));

    assertSame(failure, thrown.getCause());
  }

  @Test
  void cancelsSubscriptionOnTimeout() {
    AtomicBoolean cancelled = new AtomicBoolean();
    Publisher<String> publisher = subscriber -> subscriber.onSubscribe(subscription(cancelled));

    assertThrows(
        TimeoutException.class, () -> MongoReactiveScenario.await(publisher, Duration.ZERO));

    assertTrue(cancelled.get());
  }

  @Test
  void cancelsLateSubscriptionAfterTimeout() {
    AtomicBoolean cancelled = new AtomicBoolean();
    AtomicReference<Subscriber<? super String>> subscriber = new AtomicReference<>();
    Publisher<String> publisher = subscriber::set;

    assertThrows(
        TimeoutException.class, () -> MongoReactiveScenario.await(publisher, Duration.ZERO));
    subscriber.get().onSubscribe(subscription(cancelled));

    assertTrue(cancelled.get());
  }

  @Test
  void cancelsSubscriptionOnInterruption() {
    AtomicBoolean cancelled = new AtomicBoolean();
    Publisher<String> publisher = subscriber -> subscriber.onSubscribe(subscription(cancelled));

    Thread.currentThread().interrupt();
    try {
      assertThrows(
          InterruptedException.class,
          () -> MongoReactiveScenario.await(publisher, Duration.ofSeconds(1)));
    } finally {
      Thread.interrupted();
    }

    assertTrue(cancelled.get());
  }

  @Test
  void acceptsSynchronousCompletionWithZeroTimeout() throws Exception {
    Publisher<String> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onNext("complete");
          subscriber.onComplete();
        };

    assertEquals("complete", MongoReactiveScenario.await(publisher, Duration.ZERO));
  }

  @Test
  void closesClientAfterConsumingResult() throws Exception {
    AtomicBoolean closed = new AtomicBoolean();
    AtomicBoolean consumed = new AtomicBoolean();
    Publisher<UpdateResult> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onNext(UpdateResult.acknowledged(1, 1L, null));
          assertFalse(closed.get());
          consumed.set(true);
          subscriber.onComplete();
        };

    MongoReactiveScenario.run(client(publisher, closed), "update");

    assertTrue(consumed.get());
    assertTrue(closed.get());
  }

  @Test
  void closesClientAfterPublisherFailure() {
    AtomicBoolean closed = new AtomicBoolean();
    IllegalStateException failure = new IllegalStateException("publisher failed");
    Publisher<UpdateResult> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onError(failure);
        };

    ExecutionException thrown =
        assertThrows(
            ExecutionException.class,
            () -> MongoReactiveScenario.run(client(publisher, closed), "update"));

    assertSame(failure, thrown.getCause());
    assertTrue(closed.get());
  }

  @Test
  void closesClientAfterUnexpectedResult() {
    AtomicBoolean closed = new AtomicBoolean();
    Publisher<UpdateResult> publisher =
        subscriber -> {
          subscriber.onSubscribe(subscription(new AtomicBoolean()));
          subscriber.onNext(UpdateResult.acknowledged(0, 0L, null));
          subscriber.onComplete();
        };

    IllegalStateException thrown =
        assertThrows(
            IllegalStateException.class,
            () -> MongoReactiveScenario.run(client(publisher, closed), "update"));

    assertEquals("update matched an unexpected number of documents: 0", thrown.getMessage());
    assertTrue(closed.get());
  }

  private static Subscription subscription(AtomicBoolean cancelled) {
    return new Subscription() {
      @Override
      public void request(long count) {
        assertFalse(cancelled.get(), "requested after cancellation");
        assertEquals(Long.MAX_VALUE, count);
      }

      @Override
      public void cancel() {
        cancelled.set(true);
      }
    };
  }

  private static MongoClient client(Publisher<UpdateResult> result, AtomicBoolean closed) {
    MongoCollection<?> collection =
        proxy(
            MongoCollection.class,
            (ignored, method, arguments) -> {
              if (method.getName().equals("updateOne")) {
                return result;
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
