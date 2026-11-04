/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.reactive;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.MongoQueryException;
import com.mongodb.ServerAddress;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.result.DeleteResult;
import com.mongodb.client.result.UpdateResult;
import com.mongodb.event.CommandListener;
import com.mongodb.reactivestreams.client.MongoClient;
import com.mongodb.reactivestreams.client.MongoClients;
import com.mongodb.reactivestreams.client.MongoCollection;
import io.opentelemetry.conformance.database.mongodb.MongoContract;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;
import org.bson.Document;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

/** Exercises individual command paths against MongoDB through the reactive streams driver. */
public final class MongoReactiveScenario {
  private static final Duration TIMEOUT = Duration.ofSeconds(10);

  private MongoReactiveScenario() {}

  public static void run(String operation) throws Exception {
    run(operation, null);
  }

  public static void run(
      String operation, Function<List<ServerAddress>, CommandListener> commandListenerFactory)
      throws Exception {
    MongoClientSettings.Builder settings =
        MongoClientSettings.builder()
            .applyConnectionString(new ConnectionString(MongoContract.connectionString()));
    if (commandListenerFactory != null) {
      settings.addCommandListener(
          commandListenerFactory.apply(settings.build().getClusterSettings().getHosts()));
    }
    run(MongoClients.create(settings.build()), operation);
  }

  static void run(MongoClient client, String operation) throws Exception {
    try (client) {
      MongoCollection<Document> collection =
          client.getDatabase(MongoContract.databaseName()).getCollection(MongoContract.COLLECTION);
      switch (operation) {
        case "find":
          find(collection);
          break;
        case "update":
          update(collection);
          break;
        case "delete":
          delete(collection);
          break;
        case "aggregate":
          aggregate(collection);
          break;
        case "error":
          error(collection);
          break;
        default:
          throw new IllegalArgumentException("unknown MongoDB operation: " + operation);
      }
    }
  }

  private static void find(MongoCollection<Document> collection) throws Exception {
    Document result =
        await(collection.find(Filters.eq("_id", MongoContract.DOCUMENT_FIND)).first());
    if (result == null || !MongoContract.DOCUMENT_FIND.equals(result.getString("name"))) {
      throw new IllegalStateException("find returned an unexpected document: " + result);
    }
  }

  private static void update(MongoCollection<Document> collection) throws Exception {
    UpdateResult result =
        await(
            collection.updateOne(
                Filters.eq("_id", MongoContract.DOCUMENT_UPDATE),
                Updates.set("name", MongoContract.UPDATED_NAME)));
    if (result.getMatchedCount() != 1) {
      throw new IllegalStateException(
          "update matched an unexpected number of documents: " + result.getMatchedCount());
    }
  }

  private static void delete(MongoCollection<Document> collection) throws Exception {
    DeleteResult result =
        await(collection.deleteOne(Filters.eq("_id", MongoContract.DOCUMENT_DELETE)));
    if (result.getDeletedCount() != 1) {
      throw new IllegalStateException(
          "delete removed an unexpected number of documents: " + result.getDeletedCount());
    }
  }

  private static void aggregate(MongoCollection<Document> collection) throws Exception {
    Document result =
        await(
            collection.aggregate(
                Collections.singletonList(
                    Aggregates.match(Filters.eq("_id", MongoContract.DOCUMENT_AGGREGATE)))));
    if (result == null || !MongoContract.DOCUMENT_AGGREGATE.equals(result.getString("name"))) {
      throw new IllegalStateException("aggregate returned an unexpected document: " + result);
    }
  }

  private static void error(MongoCollection<Document> collection) throws Exception {
    try {
      await(collection.find(new Document("_id", new Document("$invalid", 1))).first());
    } catch (ExecutionException error) {
      if (!(error.getCause() instanceof MongoQueryException failure)
          || failure.getCode() != 2
          || !failure.getErrorMessage().contains("unknown operator: $invalid")) {
        throw error;
      }
      return;
    }
    throw new IllegalStateException("MongoDB accepted an invalid find filter");
  }

  private static <T> T await(Publisher<T> publisher) throws Exception {
    return await(publisher, TIMEOUT);
  }

  static <T> T await(Publisher<T> publisher, Duration timeout) throws Exception {
    CompletableFuture<T> future = new CompletableFuture<>();
    AtomicReference<Subscription> subscription = new AtomicReference<>();
    publisher.subscribe(
        new Subscriber<T>() {
          private volatile T result;

          @Override
          public void onSubscribe(Subscription value) {
            subscription.set(value);
            if (future.isCancelled()) {
              value.cancel();
            } else {
              value.request(Long.MAX_VALUE);
            }
          }

          @Override
          public void onNext(T item) {
            result = item;
          }

          @Override
          public void onError(Throwable throwable) {
            future.completeExceptionally(throwable);
          }

          @Override
          public void onComplete() {
            future.complete(result);
          }
        });
    try {
      return future.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
    } catch (InterruptedException | TimeoutException error) {
      future.cancel(false);
      Subscription current = subscription.get();
      if (current != null) {
        current.cancel();
      }
      throw error;
    }
  }
}
