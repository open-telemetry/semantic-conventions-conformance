/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.hbase;

import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.io.IOException;
import java.util.Arrays;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.hbase.HBaseConfiguration;
import org.apache.hadoop.hbase.TableName;
import org.apache.hadoop.hbase.client.Connection;
import org.apache.hadoop.hbase.client.ConnectionFactory;
import org.apache.hadoop.hbase.client.Get;
import org.apache.hadoop.hbase.client.Put;
import org.apache.hadoop.hbase.client.Result;
import org.apache.hadoop.hbase.client.ResultScanner;
import org.apache.hadoop.hbase.client.Scan;
import org.apache.hadoop.hbase.client.Table;
import org.apache.hadoop.hbase.util.Bytes;

/** Exercises representative HBase client RPCs against a local server. */
public final class HbaseScenario {
  private static final TableName TABLE = TableName.valueOf("conformance:items");
  private static final byte[] COLUMN_FAMILY = Bytes.toBytes("data");
  private static final byte[] COLUMN = Bytes.toBytes("name");

  private HbaseScenario() {}

  public static void main(String[] args) throws IOException, InterruptedException {
    if (args.length != 1) {
      throw new IllegalArgumentException("expected one HBase operation");
    }

    Configuration configuration = HBaseConfiguration.create();
    configuration.set(
        "hbase.zookeeper.quorum", ScenarioEnvironment.require("HBASE_ZOOKEEPER_QUORUM"));
    configuration.set(
        "hbase.zookeeper.property.clientPort", ScenarioEnvironment.require("HBASE_ZOOKEEPER_PORT"));
    configuration.setInt("hbase.client.retries.number", 2);
    configuration.setInt("hbase.client.operation.timeout", 15_000);
    configuration.setInt("hbase.rpc.timeout", 5_000);
    configuration.setInt("hbase.client.scanner.timeout.period", 15_000);

    try (Connection connection = ConnectionFactory.createConnection(configuration);
        Table table = connection.getTable(TABLE)) {
      switch (args[0]) {
        case "get":
          get(table);
          break;
        case "put":
          put(table);
          break;
        case "scan":
          scan(table);
          break;
        case "batch":
          batch(table);
          break;
        default:
          throw new IllegalArgumentException("unknown HBase operation: " + args[0]);
      }
    }
  }

  private static void get(Table table) throws IOException {
    Result result = table.get(new Get(Bytes.toBytes("seed")));
    byte[] value = result.getValue(COLUMN_FAMILY, COLUMN);
    if (!Arrays.equals(value, Bytes.toBytes("seed"))) {
      throw new IllegalStateException("HBase get returned an unexpected value");
    }
  }

  private static void put(Table table) throws IOException {
    Put put = new Put(Bytes.toBytes("put-row"));
    put.addColumn(COLUMN_FAMILY, COLUMN, Bytes.toBytes("put-value"));
    table.put(put);
  }

  private static void scan(Table table) throws IOException {
    try (ResultScanner scanner = table.getScanner(new Scan())) {
      if (scanner.next() == null) {
        throw new IllegalStateException("HBase scan returned no rows");
      }
    }
  }

  private static void batch(Table table) throws IOException, InterruptedException {
    Put first = new Put(Bytes.toBytes("batch-row-1"));
    first.addColumn(COLUMN_FAMILY, COLUMN, Bytes.toBytes("first"));
    Put second = new Put(Bytes.toBytes("batch-row-2"));
    second.addColumn(COLUMN_FAMILY, COLUMN, Bytes.toBytes("second"));
    Object[] results = new Object[2];
    table.batch(Arrays.asList(first, second), results);
    if (Arrays.stream(results).anyMatch(result -> result instanceof Throwable)) {
      throw new IllegalStateException("HBase batch returned an error: " + Arrays.toString(results));
    }
  }
}
