/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.hbase;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.hadoop.hbase.TableName;
import org.apache.hadoop.hbase.TableNotFoundException;
import org.apache.hadoop.hbase.client.Connection;
import org.apache.hadoop.hbase.client.Get;
import org.apache.hadoop.hbase.client.Result;
import org.apache.hadoop.hbase.client.Table;
import org.apache.hadoop.hbase.util.Bytes;
import org.junit.jupiter.api.Test;

class HbaseScenarioTest {
  @Test
  void acceptsOnlyTheExpectedMissingTableFailure() throws IOException {
    AtomicBoolean closed = new AtomicBoolean();

    HbaseScenario.error(
        connection(new TableNotFoundException("conformance:missing"), null, closed));

    assertTrue(closed.get());
  }

  @Test
  void rejectsUnexpectedSuccess() {
    AtomicBoolean closed = new AtomicBoolean();

    IllegalStateException failure =
        assertThrows(
            IllegalStateException.class, () -> HbaseScenario.error(connection(null, null, closed)));

    assertEquals("expected TableNotFoundException", failure.getMessage());
    assertTrue(closed.get());
  }

  @Test
  void propagatesOtherRequestFailures() {
    IOException failure = new IOException("request failed");
    AtomicBoolean closed = new AtomicBoolean();

    assertSame(
        failure,
        assertThrows(
            IOException.class, () -> HbaseScenario.error(connection(failure, null, closed))));
    assertTrue(closed.get());
  }

  @Test
  void propagatesCloseFailureAfterTheExpectedRequestFailure() {
    IOException failure = new IOException("close failed");
    AtomicBoolean closed = new AtomicBoolean();

    assertSame(
        failure,
        assertThrows(
            IOException.class,
            () ->
                HbaseScenario.error(
                    connection(
                        new TableNotFoundException("conformance:missing"), failure, closed))));
    assertTrue(closed.get());
  }

  private static Connection connection(
      IOException requestFailure, IOException closeFailure, AtomicBoolean closed) {
    Table table =
        hbase(
            Table.class,
            (proxy, method, arguments) -> {
              switch (method.getName()) {
                case "get":
                  assertArrayEquals(Bytes.toBytes("seed"), ((Get) arguments[0]).getRow());
                  if (requestFailure != null) {
                    throw requestFailure;
                  }
                  return Result.EMPTY_RESULT;
                case "close":
                  closed.set(true);
                  if (closeFailure != null) {
                    throw closeFailure;
                  }
                  return null;
                default:
                  throw new AssertionError(method);
              }
            });
    return hbase(
        Connection.class,
        (proxy, method, arguments) -> {
          if (!method.getName().equals("getTable")) {
            throw new AssertionError(method);
          }
          assertEquals(TableName.valueOf("conformance:missing"), arguments[0]);
          return table;
        });
  }

  private static <T> T hbase(Class<T> type, InvocationHandler handler) {
    return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, handler));
  }
}
