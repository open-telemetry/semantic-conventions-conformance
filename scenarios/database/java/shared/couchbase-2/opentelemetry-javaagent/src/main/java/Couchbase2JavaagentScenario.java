/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import com.couchbase.client.core.env.NetworkResolution;
import com.couchbase.client.java.Bucket;
import com.couchbase.client.java.CouchbaseCluster;
import com.couchbase.client.java.document.JsonDocument;
import com.couchbase.client.java.document.json.JsonObject;
import com.couchbase.client.java.env.DefaultCouchbaseEnvironment;
import com.couchbase.client.java.error.DocumentDoesNotExistException;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;

public final class Couchbase2JavaagentScenario {
  private Couchbase2JavaagentScenario() {}

  public static void main(String[] args) {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one Couchbase operation argument");
    }

    DefaultCouchbaseEnvironment environment =
        DefaultCouchbaseEnvironment.builder()
            .bootstrapHttpDirectPort(port("COUCHBASE_MANAGEMENT_PORT"))
            .bootstrapCarrierDirectPort(port("COUCHBASE_KV_PORT"))
            .networkResolution(NetworkResolution.EXTERNAL)
            .build();
    CouchbaseCluster cluster =
        CouchbaseCluster.create(environment, ScenarioEnvironment.require("DATABASE_HOST"));
    try {
      cluster.authenticate(
          ScenarioEnvironment.require("DATABASE_USER"),
          ScenarioEnvironment.require("DATABASE_PASSWORD"));
      Bucket bucket = cluster.openBucket(ScenarioEnvironment.require("DATABASE_NAME"));
      try {
        run(bucket, args[0]);
      } finally {
        bucket.close();
      }
    } finally {
      try {
        cluster.disconnect();
      } finally {
        environment.shutdown();
      }
    }
  }

  private static int port(String name) {
    return Integer.parseInt(ScenarioEnvironment.require(name));
  }

  private static void run(Bucket bucket, String operation) {
    switch (operation) {
      case "upsert":
        upsert(bucket);
        break;
      case "get":
        get(bucket);
        break;
      case "get_missing":
        getMissing(bucket);
        break;
      default:
        throw new IllegalArgumentException("unknown Couchbase 2.x operation: " + operation);
    }
  }

  private static void upsert(Bucket bucket) {
    JsonDocument stored =
        bucket.upsert(
            JsonDocument.create(
                "otel-conformance-v2-upsert", JsonObject.create().put("value", "stored")));
    if (!"stored".equals(stored.content().getString("value"))) {
      throw new IllegalStateException("Couchbase 2.x upsert returned an unexpected document");
    }
  }

  private static void get(Bucket bucket) {
    String id = "otel-conformance-v2-get";
    bucket.upsert(JsonDocument.create(id, JsonObject.create().put("value", "found")));
    JsonDocument found = bucket.get(id);
    if (found == null || !"found".equals(found.content().getString("value"))) {
      throw new IllegalStateException("Couchbase 2.x get returned an unexpected document");
    }
  }

  private static void getMissing(Bucket bucket) {
    try {
      bucket.remove("otel-conformance-v2-missing");
      throw new IllegalStateException("Couchbase 2.x remove unexpectedly succeeded");
    } catch (DocumentDoesNotExistException expected) {
      // The failed client call is the operation measured by this scenario.
    }
  }
}
