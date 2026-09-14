/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb;

import io.opentelemetry.conformance.scenario.ScenarioEnvironment;

/** Shared MongoDB connection and fixture values. */
public final class MongoContract {
  private MongoContract() {}

  public static final String COLLECTION = "items";
  public static final String DOCUMENT_FIND = "find";
  public static final String DOCUMENT_UPDATE = "update";
  public static final String DOCUMENT_DELETE = "delete";
  public static final String DOCUMENT_AGGREGATE = "aggregate";
  public static final String UPDATED_NAME = "after";

  public static String connectionString() {
    return "mongodb://"
        + ScenarioEnvironment.require("DATABASE_USER")
        + ":"
        + ScenarioEnvironment.require("DATABASE_PASSWORD")
        + "@"
        + ScenarioEnvironment.require("DATABASE_HOST")
        + ":"
        + ScenarioEnvironment.require("DATABASE_PORT")
        + "/"
        + ScenarioEnvironment.require("DATABASE_NAME");
  }

  public static String databaseName() {
    return ScenarioEnvironment.require("DATABASE_NAME");
  }
}
