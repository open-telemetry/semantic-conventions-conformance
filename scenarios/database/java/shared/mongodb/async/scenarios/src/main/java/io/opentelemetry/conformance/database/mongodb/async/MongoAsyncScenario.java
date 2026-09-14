/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.async;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.async.SingleResultCallback;
import com.mongodb.async.client.MongoClient;
import com.mongodb.async.client.MongoClients;
import com.mongodb.async.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.result.DeleteResult;
import com.mongodb.client.result.UpdateResult;
import com.mongodb.event.CommandListener;
import io.opentelemetry.conformance.database.mongodb.MongoContract;
import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.bson.Document;

/** Exercises individual command paths against MongoDB through the legacy asynchronous driver. */
public final class MongoAsyncScenario {
  private static final Duration TIMEOUT = Duration.ofSeconds(10);

  private MongoAsyncScenario() {}

  public static void run(String operation) throws Exception {
    run(operation, null);
  }

  public static void run(String operation, CommandListener commandListener) throws Exception {
    MongoClientSettings.Builder settings =
        MongoClientSettings.builder()
            .applyConnectionString(new ConnectionString(MongoContract.connectionString()));
    if (commandListener != null) {
      settings.addCommandListener(commandListener);
    }
    MongoClient client = MongoClients.create(settings.build());
    try {
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
        default:
          throw new IllegalArgumentException("unknown MongoDB operation: " + operation);
      }
    } finally {
      client.close();
    }
  }

  private static void find(MongoCollection<Document> collection) throws Exception {
    Document result =
        await(
            callback ->
                collection.find(Filters.eq("_id", MongoContract.DOCUMENT_FIND)).first(callback));
    if (result == null || !MongoContract.DOCUMENT_FIND.equals(result.getString("name"))) {
      throw new IllegalStateException("find returned an unexpected document: " + result);
    }
  }

  private static void update(MongoCollection<Document> collection) throws Exception {
    UpdateResult result =
        await(
            callback ->
                collection.updateOne(
                    Filters.eq("_id", MongoContract.DOCUMENT_UPDATE),
                    Updates.set("name", MongoContract.UPDATED_NAME),
                    callback));
    if (result.getMatchedCount() != 1) {
      throw new IllegalStateException(
          "update matched an unexpected number of documents: " + result.getMatchedCount());
    }
  }

  private static void delete(MongoCollection<Document> collection) throws Exception {
    DeleteResult result =
        await(
            callback ->
                collection.deleteOne(Filters.eq("_id", MongoContract.DOCUMENT_DELETE), callback));
    if (result.getDeletedCount() != 1) {
      throw new IllegalStateException(
          "delete removed an unexpected number of documents: " + result.getDeletedCount());
    }
  }

  private static void aggregate(MongoCollection<Document> collection) throws Exception {
    Document result =
        await(
            callback ->
                collection
                    .aggregate(
                        Collections.singletonList(
                            Aggregates.match(Filters.eq("_id", MongoContract.DOCUMENT_AGGREGATE))))
                    .first(callback));
    if (result == null || !MongoContract.DOCUMENT_AGGREGATE.equals(result.getString("name"))) {
      throw new IllegalStateException("aggregate returned an unexpected document: " + result);
    }
  }

  private static <T> T await(Consumer<SingleResultCallback<T>> action) throws Exception {
    CompletableFuture<T> future = new CompletableFuture<>();
    action.accept(
        (result, throwable) -> {
          if (throwable != null) {
            future.completeExceptionally(throwable);
          } else {
            future.complete(result);
          }
        });
    return future.get(TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
  }
}
