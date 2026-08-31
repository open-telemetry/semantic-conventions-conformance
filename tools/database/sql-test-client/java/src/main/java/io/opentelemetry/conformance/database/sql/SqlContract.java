/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.sql;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.function.IntFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The SQL database workload shared by every language.
 *
 * <p>The build copies each file under {@code tools/database/sql-test-client/contracts} onto the
 * classpath. A backend contract owns its named scenarios, exact SQL, and parameters. Client
 * adapters only translate those operations into their native APIs.
 */
public final class SqlContract {

  private static final String RESOURCE_DIRECTORY = "/otel-sql-contracts/";
  private static final Pattern BACKEND_NAME = Pattern.compile("[a-z][a-z0-9_]*");
  private static final Pattern PARAMETER_MARKER = Pattern.compile("\\$\\{([A-Za-z][A-Za-z0-9_]*)}");
  private static final ObjectMapper MAPPER =
      new ObjectMapper().disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

  private SqlContract() {}

  /** The workload described by one SQL database backend's contract. */
  public static Workload workload(String backend) {
    Objects.requireNonNull(backend, "backend");
    if (!BACKEND_NAME.matcher(backend).matches()) {
      throw new IllegalArgumentException("invalid SQL database backend: " + backend);
    }
    return load(backend);
  }

  /** One backend's named SQL scenarios. */
  public record Workload(String backend, String description, List<? extends Operation> scenarios) {
    public Workload {
      backend = requireText(backend, "backend");
      description = requireText(description, "description");
      scenarios = List.copyOf(Objects.requireNonNull(scenarios, "scenarios"));
      Set<String> names = new HashSet<>();
      for (Operation operation : scenarios) {
        if (!names.add(operation.name())) {
          throw new IllegalArgumentException("duplicate SQL scenario: " + operation.name());
        }
      }
    }

    /** Finds a named scenario or rejects a name outside the backend contract. */
    public Operation scenario(String name) {
      return scenarios.stream()
          .filter(operation -> operation.name().equals(name))
          .findFirst()
          .orElseThrow(() -> new IllegalArgumentException("unknown SQL scenario: " + name));
    }
  }

  /** A named SQL scenario expressed as one client operation. */
  public sealed interface Operation permits Query, PreparedQuery, Batch, StoredProcedure {
    String name();

    String description();
  }

  /** A direct query. */
  public record Query(String name, String description, String sql) implements Operation {
    public Query {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      sql = requireText(sql, name + " SQL");
    }
  }

  /** A prepared query with ordered named parameters. */
  public record PreparedQuery(
      String name, String description, String sql, List<Parameter> parameters)
      implements Operation {
    public PreparedQuery {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      sql = requireText(sql, name + " SQL");
      parameters = List.copyOf(Objects.requireNonNull(parameters, "parameters"));
      if (parameters.isEmpty()) {
        throw new IllegalArgumentException(name + " must declare at least one parameter");
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
  public record Batch(String name, String description, List<String> statements)
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
    }
  }

  /** A stored procedure call. */
  public record StoredProcedure(String name, String description, String procedure)
      implements Operation {
    public StoredProcedure {
      name = requireText(name, "operation name");
      description = requireText(description, name + " description");
      procedure = requireText(procedure, name + " procedure");
    }
  }

  private record Document(String backend, String description, List<ScenarioEntry> scenarios) {
    Document {
      backend = requireText(backend, "backend");
      if (!BACKEND_NAME.matcher(backend).matches()) {
        throw new IllegalArgumentException("invalid SQL database backend: " + backend);
      }
      description = requireText(description, "description");
      scenarios = List.copyOf(Objects.requireNonNull(scenarios, "scenarios"));
      if (scenarios.isEmpty()) {
        throw new IllegalArgumentException("the SQL contract must declare a scenario");
      }

      Set<String> scenarioNames = new HashSet<>();
      for (ScenarioEntry scenario : scenarios) {
        if (!scenarioNames.add(scenario.name())) {
          throw new IllegalArgumentException("duplicate SQL scenario: " + scenario.name());
        }
      }
    }

    Workload workload() {
      return new Workload(
          backend, description, scenarios.stream().map(ScenarioEntry::resolve).toList());
    }
  }

  private record ScenarioEntry(
      String name,
      String description,
      String kind,
      String sql,
      List<ParameterEntry> parameters,
      List<String> statements,
      String procedure) {

    Operation resolve() {
      String scenarioName = requireText(name, "scenario name");
      String scenarioDescription = requireText(description, scenarioName + " description");
      return switch (requireText(kind, scenarioName + " kind")) {
        case "query" ->
            new Query(scenarioName, scenarioDescription, requireText(sql, scenarioName + " SQL"));
        case "prepared_query" ->
            new PreparedQuery(
                scenarioName,
                scenarioDescription,
                requireText(sql, scenarioName + " SQL"),
                parameterEntries(scenarioName).stream().map(ParameterEntry::parameter).toList());
        case "batch" -> new Batch(scenarioName, scenarioDescription, statements);
        case "stored_procedure" ->
            new StoredProcedure(
                scenarioName,
                scenarioDescription,
                requireText(procedure, scenarioName + " procedure"));
        default ->
            throw new IllegalArgumentException(
                "unknown SQL operation kind for " + scenarioName + ": " + kind);
      };
    }

    private List<ParameterEntry> parameterEntries(String scenarioName) {
      if (parameters == null) {
        throw new IllegalArgumentException(scenarioName + " must declare parameters");
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

  private static String requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " must not be blank");
    }
    return value;
  }

  private static Workload load(String backend) {
    String resource = RESOURCE_DIRECTORY + backend + ".json";
    try (InputStream stream = SqlContract.class.getResourceAsStream(resource)) {
      if (stream == null) {
        throw new IllegalStateException(
            resource
                + " is not on the classpath; the build copies contracts from"
                + " tools/database/sql-test-client/contracts");
      }
      Document document = MAPPER.readValue(stream, Document.class);
      if (!document.backend().equals(backend)) {
        throw new IllegalArgumentException(
            resource + " declares backend " + document.backend() + " instead of " + backend);
      }
      return document.workload();
    } catch (IOException error) {
      throw new UncheckedIOException("could not read " + resource, error);
    }
  }
}
