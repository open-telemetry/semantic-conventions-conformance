/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.sync;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.result.DeleteResult;
import com.mongodb.client.result.UpdateResult;
import com.mongodb.event.CommandListener;
import io.opentelemetry.conformance.database.mongodb.MongoContract;
import java.util.Collections;
import org.bson.Document;

/** Exercises individual command paths against MongoDB through the synchronous driver. */
public final class MongoSyncScenario {
  private MongoSyncScenario() {}

  public static void run(String operation) {
    run(operation, null);
  }

  public static void run(String operation, CommandListener commandListener) {
    MongoClientSettings.Builder settings =
        MongoClientSettings.builder()
            .applyConnectionString(new ConnectionString(MongoContract.connectionString()));
    if (commandListener != null) {
      settings.addCommandListener(commandListener);
    }
    try (MongoClient client = MongoClients.create(settings.build())) {
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
    }
  }

  private static void find(MongoCollection<Document> collection) {
    Document result = collection.find(Filters.eq("_id", MongoContract.DOCUMENT_FIND)).first();
    if (result == null || !MongoContract.DOCUMENT_FIND.equals(result.getString("name"))) {
      throw new IllegalStateException("find returned an unexpected document: " + result);
    }
  }

  private static void update(MongoCollection<Document> collection) {
    UpdateResult result =
        collection.updateOne(
            Filters.eq("_id", MongoContract.DOCUMENT_UPDATE),
            Updates.set("name", MongoContract.UPDATED_NAME));
    if (result.getMatchedCount() != 1) {
      throw new IllegalStateException(
          "update matched an unexpected number of documents: " + result.getMatchedCount());
    }
  }

  private static void delete(MongoCollection<Document> collection) {
    DeleteResult result = collection.deleteOne(Filters.eq("_id", MongoContract.DOCUMENT_DELETE));
    if (result.getDeletedCount() != 1) {
      throw new IllegalStateException(
          "delete removed an unexpected number of documents: " + result.getDeletedCount());
    }
  }

  private static void aggregate(MongoCollection<Document> collection) {
    Document result =
        collection
            .aggregate(
                Collections.singletonList(
                    Aggregates.match(Filters.eq("_id", MongoContract.DOCUMENT_AGGREGATE))))
            .first();
    if (result == null || !MongoContract.DOCUMENT_AGGREGATE.equals(result.getString("name"))) {
      throw new IllegalStateException("aggregate returned an unexpected document: " + result);
    }
  }
}
