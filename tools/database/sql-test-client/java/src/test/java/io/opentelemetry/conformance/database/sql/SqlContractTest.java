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
              .filter(name -> name.endsWith(".yaml"))
              .map(name -> name.substring(0, name.length() - ".yaml".length()))
              .sorted()
              .toList();
    }

    assertFalse(backends.isEmpty());
    for (String backend : backends) {
      Workload workload = SqlContract.workload(backend);
      assertEquals(backend, workload.backend());
      assertFalse(workload.description().isBlank());
      assertFalse(workload.scenarios().isEmpty());
      assertTrue(
          workload.scenarios().stream()
              .map(SqlContract.Operation::description)
              .noneMatch(String::isBlank));
      for (int index = 0; index < workload.scenarios().size(); index++) {
        assertEquals(index, workload.scenarios().get(index).index());
      }
    }
  }

  @Test
  void resolvesPostgresqlForAClientAdapter() {
    Workload workload = SqlContract.workload("postgresql");

    Query query = assertInstanceOf(Query.class, workload.scenario(0));
    assertEquals("SELECT count(*) >= 0 FROM conformance.items", query.sql());

    PreparedQuery prepared = assertInstanceOf(PreparedQuery.class, workload.scenario(1));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = ?", prepared.renderSql(index -> "?"));
    assertEquals(
        "SELECT name FROM conformance.items WHERE id = $1",
        prepared.renderSql(index -> "$" + index));
    assertEquals(-1, prepared.parameters().get(0).integer());

    Batch batch = assertInstanceOf(Batch.class, workload.scenario(2));
    assertEquals(2, batch.statements().size());

    StoredProcedure procedure = assertInstanceOf(StoredProcedure.class, workload.scenario(3));
    assertEquals("conformance.noop", procedure.procedure());
  }

  @Test
  void rendersEveryParameterOccurrenceWithItsOwnBindMarker() {
    PreparedQuery query =
        new PreparedQuery(
            0,
            "Uses one value twice.",
            "SELECT ${id} = ${id}",
            List.of(new Parameter("id", 1), new Parameter("id", 1)));

    assertEquals("SELECT $1 = $2", query.renderSql(index -> "$" + index));
  }

  @Test
  void allowsDuplicateDescriptions() {
    Workload workload =
        new Workload(
            "postgresql",
            "Duplicate labels.",
            List.of(
                new Query(0, "Same label.", "SELECT 1"), new Query(1, "Same label.", "SELECT 2")));

    assertEquals(workload.scenario(0).description(), workload.scenario(1).description());
  }

  @Test
  void rejectsIndexesOutsideTheContract() {
    assertThrows(
        IllegalArgumentException.class, () -> SqlContract.workload("postgresql").scenario(-1));
    assertThrows(
        IllegalArgumentException.class, () -> SqlContract.workload("postgresql").scenario(4));
    assertThrows(IllegalStateException.class, () -> SqlContract.workload("no_such_backend"));
  }

  @Test
  void selectsTheScenarioTheRunnerIndexNames() {
    assertInstanceOf(Query.class, SqlContract.selectedScenario("postgresql", "0"));
    assertInstanceOf(Batch.class, SqlContract.selectedScenario("postgresql", "2"));
  }

  @Test
  void rejectsAScenarioIndexTheRunnerWouldNeverSet() {
    for (String raw : new String[] {null, "", " ", "one", "01", "-1", "1.0", "99999999999"}) {
      assertThrows(
          IllegalStateException.class, () -> SqlContract.selectedScenario("postgresql", raw), raw);
    }
    assertThrows(
        IllegalArgumentException.class, () -> SqlContract.selectedScenario("postgresql", "4"));
  }
}
