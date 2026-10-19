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
import java.util.Collections;
import java.util.List;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

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
                  "sql": "SELECT name FROM items WHERE id = ${1}",
                  "parameters": [
                    {"type": "integer", "value": -1}
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
                "{\"kind\":\"stored_procedure\",\"sql\":\"CALL conformance.noop()\"}"));
    assertEquals("CALL conformance.noop()", procedure.sql());
  }

  @Test
  void rejectsMalformedActionJson() {
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
    assertEquals(
        "OTEL_CONFORMANCE_SCENARIO_ACTION must contain a JSON object",
        assertThrows(IllegalArgumentException.class, () -> SqlContract.parseAction(" "))
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
        "query SQL must be a string",
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
        "stored procedure SQL must be a string",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"stored_procedure\"}"))
            .getMessage());
  }

  @Test
  void rejectsProcedureNameFields() {
    assertEquals(
        "stored procedure has unknown field(s): [procedure]",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "stored_procedure",
                          "sql": "CALL conformance.noop()",
                          "procedure": "conformance.noop"
                        }
                        """))
            .getMessage());
  }

  @Test
  void rejectsInvalidParameters() {
    assertEquals(
        "prepared query parameter[0] has unsupported parameter type: string",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "prepared_query",
                          "sql": "SELECT ${1}",
                          "parameters": [
                            {"type": "string", "value": "1"}
                          ]
                        }
                        """))
            .getMessage());
    assertEquals(
        "prepared query parameter[0] must have an integer value",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "prepared_query",
                          "sql": "SELECT ${1}",
                          "parameters": [
                            {"type": "integer", "value": 1.0}
                          ]
                        }
                        """))
            .getMessage());
  }

  @Test
  void rejectsNamedParameterDeclarations() {
    assertEquals(
        "prepared query parameter[0] has unknown field(s): [name]",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        """
                        {
                          "kind": "prepared_query",
                          "sql": "SELECT ${1}",
                          "parameters": [
                            {"name": "id", "type": "integer", "value": 1}
                          ]
                        }
                        """))
            .getMessage());
  }

  @ParameterizedTest
  @ValueSource(strings = {"", " "})
  void rejectsBlankTextConsistentlyInJsonAndRecords(String value) {
    assertEquals(
        assertThrows(IllegalArgumentException.class, () -> new Query(value)).getMessage(),
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"query\",\"sql\":\"" + value + "\"}"))
            .getMessage());
    assertEquals(
        assertThrows(
                IllegalArgumentException.class,
                () -> new PreparedQuery(value, List.of(new Parameter(1))))
            .getMessage(),
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"prepared_query\",\"sql\":\""
                            + value
                            + "\",\"parameters\":[{\"type\":\"integer\",\"value\":1}]}"))
            .getMessage());
    assertEquals(
        assertThrows(IllegalArgumentException.class, () -> new Batch(List.of(value))).getMessage(),
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"batch\",\"statements\":[\"" + value + "\"]}"))
            .getMessage());
    assertEquals(
        assertThrows(IllegalArgumentException.class, () -> new StoredProcedure(value)).getMessage(),
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"stored_procedure\",\"sql\":\"" + value + "\"}"))
            .getMessage());
  }

  @ParameterizedTest
  @ValueSource(strings = {"null", "42", "true", "[]", "{}"})
  void rejectsNonStringJsonValues(String value) {
    assertEquals(
        "query SQL must be a string",
        assertThrows(
                IllegalArgumentException.class,
                () -> SqlContract.parseAction("{\"kind\":\"query\",\"sql\":" + value + "}"))
            .getMessage());
    assertEquals(
        "batch statement[0] must be a string",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction("{\"kind\":\"batch\",\"statements\":[" + value + "]}"))
            .getMessage());
    assertEquals(
        "prepared query parameter[0] type must be a string",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"prepared_query\",\"sql\":\"SELECT ${1}\","
                            + "\"parameters\":[{\"type\":"
                            + value
                            + ",\"value\":1}]}"))
            .getMessage());
    assertEquals(
        "stored procedure SQL must be a string",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"stored_procedure\",\"sql\":" + value + "}"))
            .getMessage());
  }

  @Test
  void rendersNumberedPlaceholdersForDifferentDrivers() {
    PreparedQuery query =
        assertInstanceOf(
            PreparedQuery.class,
            SqlContract.parseAction(
                """
                {
                  "kind": "prepared_query",
                  "sql": "SELECT ${1} = ${2}",
                  "parameters": [
                    {"type": "integer", "value": 7},
                    {"type": "integer", "value": -2}
                  ]
                }
                """));

    assertEquals("SELECT ? = ?", query.renderSql(index -> "?"));
    assertEquals("SELECT $1 = $2", query.renderSql(index -> "$" + index));
    assertEquals("SELECT %s = %s", query.renderSql(index -> "%s"));
    assertEquals(List.of(new Parameter(7), new Parameter(-2)), query.parameters());
  }

  @ParameterizedTest
  @ValueSource(strings = {"${2}, ${1}", "${1}, ${1}", "${1}, ${3}", "${2}, ${2}"})
  void rejectsRepeatedSkippedAndOutOfOrderPlaceholders(String placeholders) {
    assertTrue(
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    new PreparedQuery(
                        "SELECT " + placeholders, List.of(new Parameter(1), new Parameter(2))))
            .getMessage()
            .startsWith("prepared query SQL placeholders must appear once in ascending order:"));
  }

  @ParameterizedTest
  @ValueSource(
      strings = {
        "${id}",
        "${user-id}",
        "${ id }",
        "${}",
        "${0}",
        "${01}",
        "${+1}",
        "${-1}",
        "${1.0}",
        "${ 1 }",
        "${2147483648}",
        "${\u0661}",
        "${2",
        "${",
        "${${2}}"
      })
  void rejectsMalformedPlaceholdersEvenAfterAValidOne(String placeholder) {
    IllegalArgumentException error =
        assertThrows(
            IllegalArgumentException.class,
            () -> new PreparedQuery("SELECT ${1}, " + placeholder, List.of(new Parameter(1))));
    assertTrue(
        error
            .getMessage()
            .startsWith(
                "prepared query SQL placeholders must appear once in ascending order: expected ${2}, got "));
    assertEquals(
        error.getMessage(),
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    SqlContract.parseAction(
                        "{\"kind\":\"prepared_query\",\"sql\":\"SELECT ${1}, "
                            + placeholder
                            + "\",\"parameters\":[{\"type\":\"integer\",\"value\":1}]}"))
            .getMessage());
  }

  @ParameterizedTest
  @CsvSource({"SELECT 1, 1, 0", "SELECT ${1}, 2, 1", "'SELECT ${1}, ${2}', 1, 2"})
  void requiresOnePlaceholderPerParameter(String sql, int parameterCount, int placeholderCount) {
    assertEquals(
        "prepared query declares "
            + parameterCount
            + " parameter(s), but SQL contains "
            + placeholderCount
            + " placeholder(s)",
        assertThrows(
                IllegalArgumentException.class,
                () -> new PreparedQuery(sql, Collections.nCopies(parameterCount, new Parameter(1))))
            .getMessage());
  }

  @Test
  void rejectsEmptyParameterLists() {
    assertEquals(
        "prepared query must declare at least one parameter",
        assertThrows(IllegalArgumentException.class, () -> new PreparedQuery("SELECT 1", List.of()))
            .getMessage());
  }

  @Test
  void rendersMultiDigitPlaceholders() {
    PreparedQuery query =
        new PreparedQuery(
            "SELECT ${1}, ${2}, ${3}, ${4}, ${5}, ${6}, ${7}, ${8}, ${9}, ${10}",
            IntStream.rangeClosed(1, 10).mapToObj(Parameter::new).toList());

    assertEquals(
        "SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10", query.renderSql(index -> "$" + index));
  }

  @Test
  void leavesQuestionMarksAndOtherSqlUntouched() {
    PreparedQuery query =
        new PreparedQuery(
            "SELECT '?' FROM items WHERE data ? 'key' AND id = ${1} /* ? */ -- ?",
            List.of(new Parameter(7)));

    assertEquals(
        "SELECT '?' FROM items WHERE data ? 'key' AND id = $1 /* ? */ -- ?",
        query.renderSql(index -> "$" + index));
  }

  @Test
  void reservesPlaceholderSyntaxEvenInsideSqlStringsAndComments() {
    assertEquals(
        "SELECT '$1', $2 /* $3 */",
        new PreparedQuery(
                "SELECT '${1}', ${2} /* ${3} */",
                List.of(new Parameter(1), new Parameter(2), new Parameter(3)))
            .renderSql(index -> "$" + index));
  }

  @Test
  void rejectsUnterminatedPlaceholdersAcrossLines() {
    assertEquals(
        "prepared query SQL placeholders must appear once in ascending order: expected ${2}, got ${2\n",
        assertThrows(
                IllegalArgumentException.class,
                () ->
                    new PreparedQuery(
                        "SELECT ${1}, ${2\n", List.of(new Parameter(1), new Parameter(2))))
            .getMessage());
  }
}
