/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.sql;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.function.IntFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.IntStream;

/**
 * The SQL database workload shared by every language.
 *
 * <p>The build copies each file under {@code tools/database/sql-test-client/contracts} onto the
 * classpath. A backend contract owns its ordered SQL actions and adjacent telemetry expectations.
 * Client adapters only translate the actions into their native APIs.
 *
 * <p>Contract parsing is strict. Unknown YAML fields fail loading so every adapter must support a
 * contract addition before a shared contract uses it.
 */
public final class SqlContract {

  /** The environment variable carrying the scenario's zero-based contract position. */
  public static final String SCENARIO_INDEX_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_INDEX";

  private static final String RESOURCE_DIRECTORY = "/otel-sql-contracts/";
  private static final Pattern BACKEND_NAME = Pattern.compile("[a-z][a-z0-9_]*");
  private static final Pattern PARAMETER_MARKER = Pattern.compile("\\$\\{([A-Za-z][A-Za-z0-9_]*)}");
  private static final Pattern SCENARIO_INDEX = Pattern.compile("0|[1-9][0-9]*");
  private static final ObjectMapper MAPPER = new ObjectMapper(new YAMLFactory());

  private SqlContract() {}

  /** The workload described by one SQL database backend's contract. */
  public static Workload workload(String backend) {
    Objects.requireNonNull(backend, "backend");
    if (!BACKEND_NAME.matcher(backend).matches()) {
      throw new IllegalArgumentException("invalid SQL database backend: " + backend);
    }
    return load(backend);
  }

  /** The one scenario the runner selected from {@code backend}'s contract. */
  public static Operation selectedScenario(String backend) {
    return selectedScenario(backend, System.getenv(SCENARIO_INDEX_VARIABLE));
  }

  // Takes the raw value so a test can drive the parsing without an environment variable.
  static Operation selectedScenario(String backend, String rawIndex) {
    if (rawIndex == null || !SCENARIO_INDEX.matcher(rawIndex).matches()) {
      throw new IllegalStateException(
          SCENARIO_INDEX_VARIABLE
              + " must be a zero-based decimal index, got "
              + displayValue(rawIndex));
    }
    int index;
    try {
      index = Integer.parseInt(rawIndex);
    } catch (NumberFormatException error) {
      throw new IllegalStateException(
          SCENARIO_INDEX_VARIABLE
              + " is larger than any contract position: "
              + displayValue(rawIndex),
          error);
    }
    return workload(backend).scenario(index);
  }

  /** One backend's ordered SQL scenarios. */
  public record Workload(String backend, String description, List<? extends Operation> scenarios) {
    public Workload {
      backend = requireText(backend, "backend");
      description = requireText(description, "description");
      scenarios = List.copyOf(Objects.requireNonNull(scenarios, "scenarios"));
      for (int index = 0; index < scenarios.size(); index++) {
        if (scenarios.get(index).index() != index) {
          throw new IllegalArgumentException(
              "SQL scenario at index " + index + " declares index " + scenarios.get(index).index());
        }
      }
    }

    /** Finds a scenario by contract position. */
    public Operation scenario(int index) {
      if (index < 0 || index >= scenarios.size()) {
        throw new IllegalArgumentException("unknown SQL scenario index: " + index);
      }
      return scenarios.get(index);
    }
  }

  /** One indexed SQL scenario expressed as a client operation. */
  public sealed interface Operation permits Query, PreparedQuery, Batch, StoredProcedure {
    int index();

    String description();
  }

  /** A direct query. */
  public record Query(int index, String description, String sql) implements Operation {
    public Query {
      index = requireIndex(index);
      description = requireText(description, scenarioLabel(index) + " description");
      sql = requireText(sql, scenarioLabel(index) + " SQL");
    }
  }

  /** A prepared query with ordered named parameters. */
  public record PreparedQuery(int index, String description, String sql, List<Parameter> parameters)
      implements Operation {
    public PreparedQuery {
      index = requireIndex(index);
      String scenario = scenarioLabel(index);
      description = requireText(description, scenario + " description");
      sql = requireText(sql, scenario + " SQL");
      parameters = List.copyOf(Objects.requireNonNull(parameters, "parameters"));
      if (parameters.isEmpty()) {
        throw new IllegalArgumentException(scenario + " must declare at least one parameter");
      }
      List<String> markers = new ArrayList<>();
      Matcher matcher = PARAMETER_MARKER.matcher(sql);
      while (matcher.find()) {
        markers.add(matcher.group(1));
      }
      List<String> parameterNames = parameters.stream().map(Parameter::name).toList();
      if (!markers.equals(parameterNames)) {
        throw new IllegalArgumentException(
            scenario
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
  public record Batch(int index, String description, List<String> statements) implements Operation {
    public Batch {
      index = requireIndex(index);
      String scenario = scenarioLabel(index);
      description = requireText(description, scenario + " description");
      statements = List.copyOf(Objects.requireNonNull(statements, "statements"));
      if (statements.isEmpty()) {
        throw new IllegalArgumentException(scenario + " must declare at least one statement");
      }
      for (String statement : statements) {
        requireText(statement, scenario + " statement");
      }
    }
  }

  /** A stored procedure call. */
  public record StoredProcedure(int index, String description, String procedure)
      implements Operation {
    public StoredProcedure {
      index = requireIndex(index);
      description = requireText(description, scenarioLabel(index) + " description");
      procedure = requireText(procedure, scenarioLabel(index) + " procedure");
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
    }

    Workload workload() {
      return new Workload(
          backend,
          description,
          IntStream.range(0, scenarios.size())
              .mapToObj(index -> scenarios.get(index).resolve(index))
              .toList());
    }
  }

  private record ScenarioEntry(String description, ActionEntry action, JsonNode expect) {

    Operation resolve(int index) {
      String scenario = scenarioLabel(index);
      String scenarioDescription = requireText(description, scenario + " description");
      if (action == null) {
        throw new IllegalArgumentException(scenario + " must declare an action");
      }
      if (expect == null || !expect.isObject()) {
        throw new IllegalArgumentException(scenario + " must declare an expect object");
      }
      return action.resolve(index, scenarioDescription);
    }
  }

  private record ActionEntry(
      String kind,
      String sql,
      List<ParameterEntry> parameters,
      List<String> statements,
      String procedure) {

    Operation resolve(int index, String description) {
      String scenario = scenarioLabel(index);
      return switch (requireText(kind, scenario + " kind")) {
        case "query" -> new Query(index, description, requireText(sql, scenario + " SQL"));
        case "prepared_query" ->
            new PreparedQuery(
                index,
                description,
                requireText(sql, scenario + " SQL"),
                parameterEntries(scenario).stream().map(ParameterEntry::parameter).toList());
        case "batch" -> new Batch(index, description, statementEntries(scenario));
        case "stored_procedure" ->
            new StoredProcedure(
                index, description, requireText(procedure, scenario + " procedure"));
        default ->
            throw new IllegalArgumentException(
                "unknown SQL operation kind for " + scenario + ": " + kind);
      };
    }

    private List<ParameterEntry> parameterEntries(String scenario) {
      if (parameters == null) {
        throw new IllegalArgumentException(scenario + " must declare parameters");
      }
      return parameters;
    }

    private List<String> statementEntries(String scenario) {
      if (statements == null) {
        throw new IllegalArgumentException(scenario + " must declare statements");
      }
      return statements;
    }
  }

  private record ParameterEntry(String name, String type, JsonNode value) {
    Parameter parameter() {
      String parameterName = requireText(name, "parameter name");
      if (!"integer".equals(type)) {
        throw new IllegalArgumentException(
            parameterName + " has unsupported parameter type: " + type);
      }
      if (value == null || !value.isInt()) {
        throw new IllegalArgumentException(parameterName + " must declare an integer value");
      }
      return new Parameter(parameterName, value.intValue());
    }
  }

  private static String requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " must not be blank");
    }
    return value;
  }

  private static int requireIndex(int index) {
    if (index < 0) {
      throw new IllegalArgumentException("SQL scenario index must not be negative: " + index);
    }
    return index;
  }

  private static String scenarioLabel(int index) {
    return "scenario[" + index + "]";
  }

  private static String displayValue(String value) {
    return value == null ? "null" : "\"" + value + "\"";
  }

  private static Workload load(String backend) {
    String resource = RESOURCE_DIRECTORY + backend + ".yaml";
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
