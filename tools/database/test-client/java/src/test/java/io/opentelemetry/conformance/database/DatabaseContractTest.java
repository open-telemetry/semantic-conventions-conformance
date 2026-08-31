/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.database.DatabaseContract.Batch;
import io.opentelemetry.conformance.database.DatabaseContract.Parameter;
import io.opentelemetry.conformance.database.DatabaseContract.PreparedQuery;
import io.opentelemetry.conformance.database.DatabaseContract.Query;
import io.opentelemetry.conformance.database.DatabaseContract.StoredProcedure;
import io.opentelemetry.conformance.database.DatabaseContract.Workload;
import java.util.List;
import org.junit.jupiter.api.Test;

class DatabaseContractTest {

  @Test
  void everyBackendResolvesTheSameOperations() {
    assertEquals(List.of("mariadb", "postgresql"), DatabaseContract.backends());

    for (String backend : DatabaseContract.backends()) {
      Workload workload = DatabaseContract.workload(backend);

      assertEquals(
          List.of("statement", "prepared_statement", "batch", "stored_procedure"),
          workload.operations().stream().map(DatabaseContract.Operation::name).toList());
      assertTrue(
          workload.operations().stream()
              .map(DatabaseContract.Operation::description)
              .noneMatch(String::isBlank));
    }
  }

  @Test
  void resolvesPostgresqlForAClientAdapter() {
    Workload workload = DatabaseContract.workload("postgresql");

    Query query = assertInstanceOf(Query.class, workload.operation("statement"));
    assertEquals("SELECT count(*) >= 0 FROM conformance.items", query.sql());
    assertTrue(query.expected());

    PreparedQuery prepared =
        assertInstanceOf(PreparedQuery.class, workload.operation("prepared_statement"));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = ?", prepared.renderSql(index -> "?"));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = $1",
        prepared.renderSql(index -> "$" + index));
    assertEquals(-1, prepared.parameters().get(0).integer());
    assertEquals(0, prepared.expectedRows());

    Batch batch = assertInstanceOf(Batch.class, workload.operation("batch"));
    assertEquals(2, batch.statements().size());
    assertEquals(2, batch.expectedSuccessfulStatements());

    StoredProcedure procedure =
        assertInstanceOf(StoredProcedure.class, workload.operation("stored_procedure"));
    assertEquals("conformance.noop", procedure.procedure());
    assertEquals(0, procedure.expectedResultSets());
  }

  @Test
  void rendersEveryParameterOccurrenceWithItsOwnBindMarker() {
    PreparedQuery query =
        new PreparedQuery(
            "repeated",
            "Uses one value twice.",
            "SELECT ${id} = ${id}",
            List.of(new Parameter("id", 1), new Parameter("id", 1)),
            1);

    assertEquals("SELECT $1 = $2", query.renderSql(index -> "$" + index));
  }

  @Test
  void rejectsNamesOutsideTheContract() {
    assertThrows(
        IllegalArgumentException.class,
        () -> DatabaseContract.workload("postgresql").operation("x"));
    assertThrows(IllegalArgumentException.class, () -> DatabaseContract.workload("sqlite"));
  }
}
