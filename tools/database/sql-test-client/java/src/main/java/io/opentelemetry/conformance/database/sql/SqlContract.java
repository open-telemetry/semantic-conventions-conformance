/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.sql;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.function.IntFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Translates the runner-selected SQL action into client-independent operation types.
 *
 * <p>The conformance runner reads a backend's combined YAML contract, selects one scenario, and
 * injects only its action as JSON. Client adapters translate the resulting operation into their
 * native APIs.
 *
 * <p>Parsing is strict. Unknown fields, duplicate fields, mismatched types, and fields belonging to
 * a different operation kind are rejected.
 */
public final class SqlContract {

  /** The environment variable carrying the selected scenario's action as JSON. */
  public static final String SCENARIO_ACTION_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTION";

  private static final Pattern PARAMETER_MARKER = Pattern.compile("\\$\\{([A-Za-z][A-Za-z0-9_]*)}");
  private static final ObjectMapper MAPPER =
      new ObjectMapper()
          .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
          .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

  private SqlContract() {}

  /** The operation selected by the conformance runner. */
  public static Operation selectedScenario() {
    return parseAction(System.getenv(SCENARIO_ACTION_VARIABLE));
  }

  // Takes the raw value so tests can drive parsing without modifying the process environment.
  static Operation parseAction(String rawAction) {
    if (rawAction == null) {
      throw new IllegalStateException(SCENARIO_ACTION_VARIABLE + " is not set");
    }
    if (rawAction.isBlank()) {
      throw new IllegalStateException(SCENARIO_ACTION_VARIABLE + " must not be blank");
    }

    JsonNode action;
    try {
      action = MAPPER.readTree(rawAction);
    } catch (JsonProcessingException error) {
      throw new IllegalArgumentException(
          SCENARIO_ACTION_VARIABLE + " contains invalid JSON: " + error.getOriginalMessage(),
          error);
    }
    if (!action.isObject()) {
      throw new IllegalArgumentException(SCENARIO_ACTION_VARIABLE + " must contain a JSON object");
    }

    String kind = requiredText(action, "kind", "SQL action");
    return switch (kind) {
      case "query" -> query(action);
      case "prepared_query" -> preparedQuery(action);
      case "batch" -> batch(action);
      case "stored_procedure" -> storedProcedure(action);
      default -> throw new IllegalArgumentException("unknown SQL operation kind: " + kind);
    };
  }

  /** One SQL action expressed as a client operation. */
  public sealed interface Operation permits Query, PreparedQuery, Batch, StoredProcedure {}

  /** A direct query. */
  public record Query(String sql) implements Operation {
    public Query {
      sql = requireText(sql, "query SQL");
    }
  }

  /** A prepared query with ordered named parameters. */
  public record PreparedQuery(String sql, List<Parameter> parameters) implements Operation {
    public PreparedQuery {
      sql = requireText(sql, "prepared query SQL");
      parameters = List.copyOf(Objects.requireNonNull(parameters, "parameters"));
      if (parameters.isEmpty()) {
        throw new IllegalArgumentException("prepared query must declare at least one parameter");
      }
      List<String> markers = new ArrayList<>();
      Matcher matcher = PARAMETER_MARKER.matcher(sql);
      while (matcher.find()) {
        markers.add(matcher.group(1));
      }
      List<String> parameterNames = parameters.stream().map(Parameter::name).toList();
      if (!markers.equals(parameterNames)) {
        throw new IllegalArgumentException(
            "prepared query SQL markers must match its parameters in order: expected "
                + parameterNames
                + ", got "
                + markers);
      }
    }

    /**
     * Renders named contract markers as a client's positional bind markers.
     *
     * <p>The marker function receives one-based parameter indexes.
     */
    public String renderSql(IntFunction<String> bindMarker) {
      Objects.requireNonNull(bindMarker, "bindMarker");
      Matcher matcher = PARAMETER_MARKER.matcher(sql);
      StringBuilder rendered = new StringBuilder();
      int index = 0;
      while (matcher.find()) {
        String marker =
            requireText(bindMarker.apply(++index), "bind marker " + Integer.toString(index));
        matcher.appendReplacement(rendered, Matcher.quoteReplacement(marker));
      }
      matcher.appendTail(rendered);
      return rendered.toString();
    }
  }

  /** One integer bind value from a prepared query. */
  public record Parameter(String name, int integer) {
    public Parameter {
      name = requireText(name, "parameter name");
    }
  }

  /** A list of statements executed as one batch. */
  public record Batch(List<String> statements) implements Operation {
    public Batch {
      statements = List.copyOf(Objects.requireNonNull(statements, "statements"));
      if (statements.isEmpty()) {
        throw new IllegalArgumentException("batch must declare at least one statement");
      }
      for (String statement : statements) {
        requireText(statement, "batch statement");
      }
    }
  }

  /** A stored procedure call. */
  public record StoredProcedure(String procedure) implements Operation {
    public StoredProcedure {
      procedure = requireText(procedure, "stored procedure name");
    }
  }

  private static Query query(JsonNode action) {
    requireOnlyFields(action, "query", "kind", "sql");
    return new Query(requiredText(action, "sql", "query"));
  }

  private static PreparedQuery preparedQuery(JsonNode action) {
    requireOnlyFields(action, "prepared query", "kind", "sql", "parameters");
    JsonNode entries = action.get("parameters");
    if (entries == null || !entries.isArray()) {
      throw new IllegalArgumentException("prepared query parameters must be a JSON array");
    }
    List<Parameter> parameters = new ArrayList<>();
    for (int index = 0; index < entries.size(); index++) {
      JsonNode entry = entries.get(index);
      String label = "prepared query parameter[" + index + "]";
      if (!entry.isObject()) {
        throw new IllegalArgumentException(label + " must be a JSON object");
      }
      requireOnlyFields(entry, label, "name", "type", "value");
      String name = requiredText(entry, "name", label);
      String type = requiredText(entry, "type", label);
      if (!"integer".equals(type)) {
        throw new IllegalArgumentException(
            label + " " + name + " has unsupported parameter type: " + type);
      }
      JsonNode value = entry.get("value");
      if (value == null || !value.isInt()) {
        throw new IllegalArgumentException(label + " " + name + " must have an integer value");
      }
      parameters.add(new Parameter(name, value.intValue()));
    }
    return new PreparedQuery(requiredText(action, "sql", "prepared query"), parameters);
  }

  private static Batch batch(JsonNode action) {
    requireOnlyFields(action, "batch", "kind", "statements");
    JsonNode entries = action.get("statements");
    if (entries == null || !entries.isArray()) {
      throw new IllegalArgumentException("batch statements must be a JSON array");
    }
    List<String> statements = new ArrayList<>();
    for (int index = 0; index < entries.size(); index++) {
      statements.add(requiredText(entries.get(index), "batch statement[" + index + "]"));
    }
    return new Batch(statements);
  }

  private static StoredProcedure storedProcedure(JsonNode action) {
    requireOnlyFields(action, "stored procedure", "kind", "procedure");
    return new StoredProcedure(requiredText(action, "procedure", "stored procedure"));
  }

  private static void requireOnlyFields(JsonNode object, String label, String... fields) {
    Set<String> allowed = Set.of(fields);
    List<String> unknown = new ArrayList<>();
    object
        .fieldNames()
        .forEachRemaining(
            field -> {
              if (!allowed.contains(field)) {
                unknown.add(field);
              }
            });
    if (!unknown.isEmpty()) {
      unknown.sort(String::compareTo);
      throw new IllegalArgumentException(label + " has unknown field(s): " + unknown);
    }
  }

  private static String requiredText(JsonNode object, String field, String label) {
    return requiredText(object.get(field), label + " " + field);
  }

  private static String requiredText(JsonNode value, String label) {
    if (value == null || !value.isTextual() || value.textValue().isBlank()) {
      throw new IllegalArgumentException(label + " must be a non-blank string");
    }
    return value.textValue();
  }

  private static String requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " must not be blank");
    }
    return value;
  }
}
