/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.IntFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The database workload shared by every language.
 *
 * <p>The build copies {@code tools/database/test-client/contract.json} onto the classpath. The
 * contract owns backend-specific SQL, parameters, and expected results. Client adapters only
 * translate those operations into their native APIs.
 */
public final class DatabaseContract {

  private static final String RESOURCE = "/otel-database-contract.json";
  private static final Pattern BACKEND_NAME = Pattern.compile("[a-z][a-z0-9_]*");
  private static final Pattern PARAMETER_MARKER = Pattern.compile("\\$\\{([A-Za-z][A-Za-z0-9_]*)}");
  private static final ObjectMapper MAPPER =
      new ObjectMapper().disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

  private static volatile Document document;

  private DatabaseContract() {}

  /** The database backends described by the contract. */
  public static List<String> backends() {
    return document().backends();
  }

  /** The workload resolved for one database backend. */
  public static Workload workload(String backend) {
    Objects.requireNonNull(backend, "backend");
    if (!BACKEND_NAME.matcher(backend).matches()) {
      throw new IllegalArgumentException("invalid database backend: " + backend);
    }
    return document().workload(backend);
  }

  /** One backend's resolved operations. */
  public record Workload(String backend, String description, List<? extends Operation> operations) {
    public Workload {
      backend = requireText(backend, "backend");
      description = requireText(description, "description");
      operations = List.copyOf(Objects.requireNonNull(operations, "operations"));
      Set<String> names = new HashSet<>();
      for (Operation operation : operations) {
        if (!names.add(operation.name())) {
          throw new IllegalArgumentException("duplicate database operation: " + operation.name());
        }
      }
    }

    /** Finds a named operation or rejects a scenario name outside the contract. */
    public Operation operation(String name) {
      return operations.stream()
          .filter(operation -> operation.name().equals(name))
          .findFirst()
          .orElseThrow(() -> new IllegalArgumentException("unknown database operation: " + name));
    }
  }

  /** A database operation with one stable scenario name. */
  public sealed interface Operation permits Query, PreparedQuery, Batch, StoredProcedure {
    String name();

    String description();
  }

  /** A direct query with one expected Boolean value. */
  public record Query(String name, String description, String sql, boolean expected)
      implements Operation {
    public Query {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      sql = requireText(sql, name + " SQL");
    }
  }

  /** A prepared query with ordered named parameters and an expected row count. */
  public record PreparedQuery(
      String name, String description, String sql, List<Parameter> parameters, int expectedRows)
      implements Operation {
    public PreparedQuery {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      sql = requireText(sql, name + " SQL");
      parameters = List.copyOf(Objects.requireNonNull(parameters, "parameters"));
      if (parameters.isEmpty()) {
        throw new IllegalArgumentException(name + " must declare at least one parameter");
      }
      if (expectedRows < 0) {
        throw new IllegalArgumentException(name + " expected row count must not be negative");
      }

      List<String> markers = new ArrayList<>();
      Matcher matcher = PARAMETER_MARKER.matcher(sql);
      while (matcher.find()) {
        markers.add(matcher.group(1));
      }
      List<String> parameterNames = parameters.stream().map(Parameter::name).toList();
      if (!markers.equals(parameterNames)) {
        throw new IllegalArgumentException(
            name
                + " SQL markers must match its parameters in order: expected "
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
  public record Batch(
      String name, String description, List<String> statements, int expectedSuccessfulStatements)
      implements Operation {
    public Batch {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      statements = List.copyOf(Objects.requireNonNull(statements, "statements"));
      if (statements.isEmpty()) {
        throw new IllegalArgumentException(name + " must declare at least one statement");
      }
      for (String statement : statements) {
        requireText(statement, name + " statement");
      }
      if (expectedSuccessfulStatements != statements.size()) {
        throw new IllegalArgumentException(name + " expects every batch statement to succeed");
      }
    }
  }

  /** A stored procedure call with an expected result-set count. */
  public record StoredProcedure(
      String name, String description, String procedure, int expectedResultSets)
      implements Operation {
    public StoredProcedure {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      procedure = requireText(procedure, name + " procedure");
      if (expectedResultSets < 0) {
        throw new IllegalArgumentException(
            name + " expected result-set count must not be negative");
      }
    }
  }

  private record Document(
      String description, List<String> backends, List<OperationEntry> operations) {
    Document {
      description = requireText(description, "description");
      backends = List.copyOf(Objects.requireNonNull(backends, "backends"));
      operations = List.copyOf(Objects.requireNonNull(operations, "operations"));
      if (backends.isEmpty()) {
        throw new IllegalArgumentException("the database contract must declare a backend");
      }
      if (operations.isEmpty()) {
        throw new IllegalArgumentException("the database contract must declare an operation");
      }

      Set<String> backendNames = new HashSet<>();
      for (String backend : backends) {
        requireText(backend, "backend");
        if (!BACKEND_NAME.matcher(backend).matches()) {
          throw new IllegalArgumentException("invalid database backend: " + backend);
        }
        if (!backendNames.add(backend)) {
          throw new IllegalArgumentException("duplicate database backend: " + backend);
        }
      }

      Set<String> operationNames = new HashSet<>();
      for (OperationEntry operation : operations) {
        if (!operationNames.add(operation.name())) {
          throw new IllegalArgumentException("duplicate database operation: " + operation.name());
        }
        operation.validateBackends(backendNames);
        for (String backend : backends) {
          operation.resolve(backend);
        }
      }
    }

    Workload workload(String backend) {
      if (!backends.contains(backend)) {
        throw new IllegalArgumentException(
            "unsupported database backend "
                + backend
                + "; expected one of: "
                + String.join(", ", backends));
      }
      return new Workload(
          backend, description, operations.stream().map(entry -> entry.resolve(backend)).toList());
    }
  }

  private record OperationEntry(
      String name,
      String description,
      String kind,
      Map<String, String> sql,
      List<ParameterEntry> parameters,
      Map<String, List<String>> statements,
      Map<String, String> procedures,
      ExpectedEntry expect) {

    void validateBackends(Set<String> backends) {
      Map<?, ?> values =
          switch (requireText(kind, name + " kind")) {
            case "query", "prepared_query" -> sql;
            case "batch" -> statements;
            case "stored_procedure" -> procedures;
            default ->
                throw new IllegalArgumentException(
                    "unknown database operation kind for " + name + ": " + kind);
          };
      if (values == null || !values.keySet().equals(backends)) {
        throw new IllegalArgumentException(
            name + " must define its backend values for exactly: " + String.join(", ", backends));
      }
    }

    Operation resolve(String backend) {
      String operationName = requireText(name, "operation name");
      String operationDescription = requireText(description, operationName + " description");
      ExpectedEntry expected = Objects.requireNonNull(expect, operationName + " expect");
      return switch (requireText(kind, operationName + " kind")) {
        case "query" ->
            new Query(
                operationName,
                operationDescription,
                backendValue(sql, backend, operationName + " SQL"),
                expected.singleBoolean(operationName));
        case "prepared_query" ->
            new PreparedQuery(
                operationName,
                operationDescription,
                backendValue(sql, backend, operationName + " SQL"),
                parameterEntries(operationName).stream().map(ParameterEntry::parameter).toList(),
                expected.rows(operationName));
        case "batch" ->
            new Batch(
                operationName,
                operationDescription,
                backendValue(statements, backend, operationName + " statements"),
                expected.successfulStatements(operationName));
        case "stored_procedure" ->
            new StoredProcedure(
                operationName,
                operationDescription,
                backendValue(procedures, backend, operationName + " procedure"),
                expected.resultSets(operationName));
        default ->
            throw new IllegalArgumentException(
                "unknown database operation kind for " + operationName + ": " + kind);
      };
    }

    private List<ParameterEntry> parameterEntries(String operationName) {
      if (parameters == null) {
        throw new IllegalArgumentException(operationName + " must declare parameters");
      }
      return parameters;
    }
  }

  private record ParameterEntry(String name, String type, JsonNode value) {
    Parameter parameter() {
      if (!"integer".equals(type)) {
        throw new IllegalArgumentException(name + " has unsupported parameter type: " + type);
      }
      if (value == null || !value.isInt()) {
        throw new IllegalArgumentException(name + " must declare an integer value");
      }
      return new Parameter(name, value.intValue());
    }
  }

  private record ExpectedEntry(
      Boolean singleBoolean, Integer rows, Integer successfulStatements, Integer resultSets) {
    boolean singleBoolean(String operation) {
      if (singleBoolean == null) {
        throw new IllegalArgumentException(operation + " must expect one Boolean value");
      }
      return singleBoolean;
    }

    int rows(String operation) {
      return requiredCount(rows, operation, "rows");
    }

    int successfulStatements(String operation) {
      return requiredCount(successfulStatements, operation, "successfulStatements");
    }

    int resultSets(String operation) {
      return requiredCount(resultSets, operation, "resultSets");
    }
  }

  private static <T> T backendValue(Map<String, T> values, String backend, String field) {
    Objects.requireNonNull(values, field);
    T value = values.get(backend);
    if (value == null) {
      throw new IllegalArgumentException(field + " is missing for " + backend);
    }
    return value;
  }

  private static int requiredCount(Integer value, String operation, String field) {
    if (value == null) {
      throw new IllegalArgumentException(operation + " must expect " + field);
    }
    return value;
  }

  private static String requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " must not be blank");
    }
    return value;
  }

  private static Document document() {
    Document loaded = document;
    if (loaded == null) {
      loaded = load();
      document = loaded;
    }
    return loaded;
  }

  private static Document load() {
    try (InputStream stream = DatabaseContract.class.getResourceAsStream(RESOURCE)) {
      if (stream == null) {
        throw new IllegalStateException(
            RESOURCE
                + " is not on the classpath; the build copies it from"
                + " tools/database/test-client/contract.json");
      }
      return MAPPER.readValue(stream, Document.class);
    } catch (IOException error) {
      throw new UncheckedIOException("could not read " + RESOURCE, error);
    }
  }
}
