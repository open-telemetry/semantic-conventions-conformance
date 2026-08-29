/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import com.couchbase.client.core.error.DocumentNotFoundException;
import com.couchbase.client.java.Bucket;
import com.couchbase.client.java.Cluster;
import com.couchbase.client.java.Collection;
import com.couchbase.client.java.json.JsonObject;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.time.Duration;

public final class Couchbase3JavaagentScenario {
  private Couchbase3JavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Couchbase operation argument");
    }

    try (Cluster cluster =
        Cluster.connect(
            ScenarioEnvironment.require("COUCHBASE_CONNECTION_STRING"),
            ScenarioEnvironment.require("DATABASE_USER"),
            ScenarioEnvironment.require("DATABASE_PASSWORD"))) {
      Bucket bucket = cluster.bucket(ScenarioEnvironment.require("DATABASE_NAME"));
      bucket.waitUntilReady(Duration.ofSeconds(30));
      Collection collection =
          bucket
              .scope(ScenarioEnvironment.require("COUCHBASE_SCOPE"))
              .collection(ScenarioEnvironment.require("COUCHBASE_COLLECTION"));
      run(collection, args[0]);
    }
  }

  private static void run(Collection collection, String operation) {
    switch (operation) {
      case "upsert":
        upsert(collection);
        break;
      case "get":
        get(collection);
        break;
      case "get_missing":
        getMissing(collection);
        break;
      default:
        throw new IllegalArgumentException("unknown Couchbase 3.x operation: " + operation);
    }
  }

  private static void upsert(Collection collection) {
    collection.upsert("otel-conformance-v3-upsert", JsonObject.create().put("value", "stored"));
  }

  private static void get(Collection collection) {
    String id = "otel-conformance-v3-get";
    collection.upsert(id, JsonObject.create().put("value", "found"));
    String value = collection.get(id).contentAsObject().getString("value");
    if (!"found".equals(value)) {
      throw new IllegalStateException("Couchbase 3.x get returned an unexpected document");
    }
  }

  private static void getMissing(Collection collection) {
    try {
      collection.get("otel-conformance-v3-missing");
      throw new IllegalStateException("Couchbase 3.x get unexpectedly succeeded");
    } catch (DocumentNotFoundException expected) {
      // The failed client call is the operation measured by this scenario.
    }
  }
}
