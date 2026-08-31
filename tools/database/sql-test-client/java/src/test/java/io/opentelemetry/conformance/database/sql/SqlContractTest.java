/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.sql;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.database.sql.SqlContract.Batch;
import io.opentelemetry.conformance.database.sql.SqlContract.Parameter;
import io.opentelemetry.conformance.database.sql.SqlContract.PreparedQuery;
import io.opentelemetry.conformance.database.sql.SqlContract.Query;
import io.opentelemetry.conformance.database.sql.SqlContract.StoredProcedure;
import io.opentelemetry.conformance.database.sql.SqlContract.Workload;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

class SqlContractTest {

  @Test
  void loadsEveryBackendContract() throws IOException {
    List<String> backends;
    try (Stream<Path> contracts = Files.list(Path.of("../contracts"))) {
      backends =
          contracts
              .map(path -> path.getFileName().toString())
              .filter(name -> name.endsWith(".json"))
              .map(name -> name.substring(0, name.length() - ".json".length()))
              .sorted()
              .toList();
    }

    assertFalse(backends.isEmpty());
    for (String backend : backends) {
      Workload workload = SqlContract.workload(backend);
      assertEquals(backend, workload.backend());
      assertFalse(workload.scenarios().isEmpty());
      assertTrue(
          workload.scenarios().stream()
              .map(SqlContract.Operation::description)
              .noneMatch(String::isBlank));
    }
  }

  @Test
  void resolvesPostgresqlForAClientAdapter() {
    Workload workload = SqlContract.workload("postgresql");

    Query query = assertInstanceOf(Query.class, workload.scenario("statement"));
    assertEquals("SELECT count(*) >= 0 FROM conformance.items", query.sql());

    PreparedQuery prepared =
        assertInstanceOf(PreparedQuery.class, workload.scenario("prepared_statement"));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = ?", prepared.renderSql(index -> "?"));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = $1",
        prepared.renderSql(index -> "$" + index));
    assertEquals(-1, prepared.parameters().get(0).integer());

    Batch batch = assertInstanceOf(Batch.class, workload.scenario("batch"));
    assertEquals(2, batch.statements().size());

    StoredProcedure procedure =
        assertInstanceOf(StoredProcedure.class, workload.scenario("stored_procedure"));
    assertEquals("conformance.noop", procedure.procedure());
  }

  @Test
  void rendersEveryParameterOccurrenceWithItsOwnBindMarker() {
    PreparedQuery query =
        new PreparedQuery(
            "repeated",
            "Uses one value twice.",
            "SELECT ${id} = ${id}",
            List.of(new Parameter("id", 1), new Parameter("id", 1)));

    assertEquals("SELECT $1 = $2", query.renderSql(index -> "$" + index));
  }

  @Test
  void rejectsNamesOutsideTheContract() {
    assertThrows(
        IllegalArgumentException.class, () -> SqlContract.workload("postgresql").scenario("x"));
    assertThrows(IllegalStateException.class, () -> SqlContract.workload("no_such_backend"));
  }
}
