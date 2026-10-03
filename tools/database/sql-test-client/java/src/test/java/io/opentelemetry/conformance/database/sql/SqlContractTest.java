/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.sql;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.conformance.database.sql.SqlContract.Batch;
import io.opentelemetry.conformance.database.sql.SqlContract.Parameter;
import io.opentelemetry.conformance.database.sql.SqlContract.PreparedQuery;
import io.opentelemetry.conformance.database.sql.SqlContract.Query;
import io.opentelemetry.conformance.database.sql.SqlContract.StoredProcedure;
import java.util.List;
import org.junit.jupiter.api.Test;

class SqlContractTest {

  @Test
  void parsesEveryOperationKind() {
    Query query =
        assertInstanceOf(
            Query.class, SqlContract.parseAction("{\"kind\":\"query\",\"sql\":\"SELECT 1\"}"));
    assertEquals("SELECT 1", query.sql());

    PreparedQuery prepared =
        assertInstanceOf(
            PreparedQuery.class,
            SqlContract.parseAction(
                """
                {
                  "kind": "prepared_query",
                  "sql": "SELECT name FROM items WHERE id = ${id}",
                  "parameters": [
                    {"name": "id", "type": "integer", "value": -1}
                  ]
                }
                """));
    assertEquals("SELECT name FROM items WHERE id = ?", prepared.renderSql(ignored -> "?"));
    assertEquals(-1, prepared.parameters().get(0).integer());

    Batch batch =
        assertInstanceOf(
            Batch.class,
            SqlContract.parseAction(
                """
                {
                  "kind": "batch",
                  "statements": ["INSERT INTO items VALUES (1)", "DELETE FROM items"]
                }
                """));
    assertEquals(2, batch.statements().size());

    StoredProcedure procedure =
        assertInstanceOf(
            StoredProcedure.class,
            SqlContract.parseAction(
                "{\"kind\":\"stored_procedure\",\"procedure\":\"conformance.noop\"}"));
    assertEquals("conformance.noop", procedure.procedure());
  }

  @Test
  void rejectsMissingOrMalformedActionJson() {
    assertEquals(
        "OTEL_CONFORMANCE_SCENARIO_ACTION is not set",
        assertThrows(IllegalStateException.class, () -> SqlContract.parseAction(null))
            .getMessage());
    assertEquals(
        "OTEL_CONFORMANCE_SCENARIO_ACTION must not be blank",
        assertThrows(IllegalStateException.class, () -> SqlContract.parseAction(" ")).getMessage());
    assertTrue(
        assertThrows(IllegalArgumentException.class, () -> SqlContract.parseAction("{"))
            .getMessage()
            .startsWith("OTEL_CONFORMANCE_SCENARIO_ACTION contains invalid JSON:"));
    assertTrue(
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"query\",\"sql\":\"SELECT 1\"} {}"))
            .getMessage()
            .startsWith("OTEL_CONFORMANCE_SCENARIO_ACTION contains invalid JSON:"));
    assertEquals(
        "OTEL_CONFORMANCE_SCENARIO_ACTION must contain a JSON object",
        assertThrows(IllegalArgumentException.class, () -> SqlContract.parseAction("[]"))
            .getMessage());
  }

  @Test
  void rejectsUnknownAndDuplicateFields() {
    assertEquals(
        "query has unknown field(s): [statements]",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"query\",\"sql\":\"SELECT 1\",\"statements\":[]}"))
            .getMessage());
    assertTrue(
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"query\",\"sql\":\"SELECT 1\",\"sql\":\"SELECT 2\"}"))
            .getMessage()
            .startsWith("OTEL_CONFORMANCE_SCENARIO_ACTION contains invalid JSON:"));
  }

  @Test
  void rejectsAnUnknownOperationKind() {
    assertEquals(
        "unknown SQL operation kind: invalid",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"invalid\"}"))
            .getMessage());
  }

  @Test
  void rejectsMissingAndWronglyTypedOperationFields() {
    assertEquals(
        "query sql must be a non-blank string",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"query\"}"))
            .getMessage());
    assertEquals(
        "batch statements must be a JSON array",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"batch\",\"statements\":\"SELECT 1\"}"))
            .getMessage());
    assertEquals(
        "stored procedure procedure must be a non-blank string",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"stored_procedure\"}"))
            .getMessage());
  }

  @Test
  void rejectsInvalidParameters() {
    assertEquals(
        "prepared query parameter[0] id has unsupported parameter type: string",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "prepared_query",
                          "sql": "SELECT ${id}",
                          "parameters": [
                            {"name": "id", "type": "string", "value": "1"}
                          ]
                        }
                        """))
            .getMessage());
    assertEquals(
        "prepared query parameter[0] id must have an integer value",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "prepared_query",
                          "sql": "SELECT ${id}",
                          "parameters": [
                            {"name": "id", "type": "integer", "value": 1.0}
                          ]
                        }
                        """))
            .getMessage());
  }

  @Test
  void rendersEveryParameterOccurrenceWithItsOwnBindMarker() {
    PreparedQuery query =
        new PreparedQuery(
            "SELECT ${id} = ${id}", List.of(new Parameter("id", 1), new Parameter("id", 1)));

    assertEquals("SELECT $1 = $2", query.renderSql(index -> "$" + index));
  }

  @Test
  void requiresMarkersToMatchParametersInOrder() {
    assertEquals(
        "prepared query SQL markers must match its parameters in order: expected [name, id], got [id, name]",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    new PreparedQuery(
                        "SELECT ${id}, ${name}",
                        List.of(new Parameter("name", 1), new Parameter("id", 2))))
            .getMessage());
  }
}
