/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicReference;

/** The HTTP conformance exchanges supplied by the runner as JSON. */
public final class HttpContract {

  /** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
  public static final String CONTENT_TYPE = "application/json";

  /**
   * Fixed rather than the HTTP library's default, so a server scenario sees the same client
   * whichever language sent the requests.
   */
  public static final String USER_AGENT = "otel-http-conformance/1";

  public static final String ACTION_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTION";
  public static final String ACTIONS_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTIONS";

  private static final ObjectMapper JSON =
      new ObjectMapper()
          .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
          .enable(DeserializationFeature.FAIL_ON_READING_DUP_TREE_KEY);

  private HttpContract() {}

  /**
   * One concrete request and the answer the contract requires.
   *
   * <p>{@code body} is null for a request that carries none. The only substitution in {@code
   * responseBody} is the literal {@code ${requestBody}}, for the body that arrived.
   */
  public record Exchange(
      String method,
      String path,
      String body,
      int status,
      String responseBody,
      boolean readiness,
      String description) {

    /** The response body with the request body inserted. */
    public String renderResponseBody(String requestBody) {
      return responseBody.replace(
          "${requestBody}", requestBody == null || requestBody.isEmpty() ? "{}" : requestBody);
    }
  }

  /** A status and a body: what a request came back as, and what a route answers. */
  public record Response(int statusCode, String body) {}

  /** Every exchange supplied by the runner, including readiness, in order. */
  public static List<Exchange> exchanges() {
    return cachedActions(requiredEnvironment(ACTIONS_VARIABLE));
  }

  /**
   * The action table, parsed once per process.
   *
   * <p>A server scenario answers every request from this table, so parsing it per request would
   * charge the measured process on the path its instrumentation is timing. The runner sets the
   * table before the process starts and never changes it; keying the cache on the raw text keeps a
   * caller that varies it honest.
   */
  static List<Exchange> cachedActions(String raw) {
    ParsedTable cached = CACHE.get();
    if (cached != null && cached.raw().equals(raw)) {
      return cached.exchanges();
    }
    List<Exchange> parsed = loadActions(raw);
    CACHE.set(new ParsedTable(raw, parsed));
    return parsed;
  }

  private record ParsedTable(String raw, List<Exchange> exchanges) {}

  private static final AtomicReference<ParsedTable> CACHE = new AtomicReference<>();

  /** The measured requests supplied by the runner. */
  public static List<Exchange> requests() {
    List<Exchange> exchanges = exchanges();
    return exchanges.subList(1, exchanges.size());
  }

  /** The one request selected by the runner. */
  public static Exchange scenarioRequest() {
    return loadAction(requiredEnvironment(ACTION_VARIABLE));
  }

  static Exchange loadAction(String raw) {
    return exchange(parse(raw, ACTION_VARIABLE), ACTION_VARIABLE + " action", false);
  }

  static List<Exchange> loadActions(String raw) {
    JsonNode document = parse(raw, ACTIONS_VARIABLE);
    if (!document.isArray() || document.isEmpty()) {
      throw new IllegalStateException(
          ACTIONS_VARIABLE + " must be a non-empty JSON array of actions");
    }
    List<Exchange> result = new ArrayList<>();
    for (int index = 0; index < document.size(); index++) {
      result.add(
          exchange(document.get(index), ACTIONS_VARIABLE + "[" + index + "] action", index == 0));
    }
    return List.copyOf(result);
  }

  static Exchange request(int index) {
    List<Exchange> requests = requests();
    if (index < 0 || index >= requests.size()) {
      throw new IllegalArgumentException(
          "action index "
              + index
              + " selects no runner action; expected 0.."
              + (requests.size() - 1));
    }
    return requests.get(index);
  }

  /** The exchange answering {@code method path}, if the runner supplied one. */
  static Optional<Exchange> exchange(String method, String path) {
    return exchange(exchanges(), method, path);
  }

  static Optional<Exchange> exchange(List<Exchange> exchanges, String method, String path) {
    String withoutQuery = withoutQuery(path);
    return exchanges.stream()
        .filter(exchange -> exchange.method().equals(method))
        .filter(exchange -> withoutQuery(exchange.path()).equals(withoutQuery))
        .findFirst();
  }

  private static String requiredEnvironment(String variable) {
    String value = System.getenv(variable);
    if (value == null) {
      throw new IllegalStateException(variable + " is not set");
    }
    return value;
  }

  private static JsonNode parse(String raw, String variable) {
    try {
      JsonNode result = JSON.readTree(raw);
      if (result == null) {
        throw new IllegalStateException(variable + " contains no JSON value");
      }
      return result;
    } catch (JsonProcessingException error) {
      throw new IllegalStateException(
          variable + " contains malformed JSON: " + error.getMessage(), error);
    }
  }

  private static Exchange exchange(JsonNode action, String where, boolean readiness) {
    requireObject(action, where);
    checkKeys(action, Set.of("request", "response"), where);
    JsonNode request = action.get("request");
    JsonNode response = action.get("response");
    if (request == null || response == null) {
      throw new IllegalStateException(where + " requires request and response objects");
    }
    requireObject(request, where + ".request");
    requireObject(response, where + ".response");
    checkKeys(request, Set.of("method", "path", "body"), where + ".request");
    checkKeys(response, Set.of("status", "body"), where + ".response");

    String method = requiredText(request.get("method"), where + ".request.method");
    String path = requiredText(request.get("path"), where + ".request.path");
    if (!path.startsWith("/")) {
      throw new IllegalStateException(where + ".request.path must start with '/'");
    }
    JsonNode bodyNode = request.get("body");
    String body = null;
    if (bodyNode != null && !bodyNode.isNull()) {
      if (!bodyNode.isTextual()) {
        throw new IllegalStateException(where + ".request.body must be a string");
      }
      body = bodyNode.textValue();
    }
    JsonNode statusNode = response.get("status");
    if (statusNode == null
        || !statusNode.isIntegralNumber()
        || !statusNode.canConvertToInt()
        || statusNode.intValue() < 100
        || statusNode.intValue() > 599) {
      throw new IllegalStateException(where + ".response.status must be an HTTP status");
    }
    String responseBody = requiredText(response.get("body"), where + ".response.body", true);
    return new Exchange(
        method,
        path,
        body,
        statusNode.intValue(),
        responseBody,
        readiness,
        readiness ? "runner readiness action" : "runner action");
  }

  private static void requireObject(JsonNode value, String where) {
    if (!value.isObject()) {
      throw new IllegalStateException(where + " must be a JSON object");
    }
  }

  private static String requiredText(JsonNode value, String where) {
    return requiredText(value, where, false);
  }

  private static String requiredText(JsonNode value, String where, boolean allowEmpty) {
    if (value == null || !value.isTextual() || (!allowEmpty && value.textValue().isEmpty())) {
      throw new IllegalStateException(
          where + (allowEmpty ? " must be a string" : " must be a non-empty string"));
    }
    return value.textValue();
  }

  private static void checkKeys(JsonNode value, Set<String> allowed, String where) {
    Iterator<String> fields = value.fieldNames();
    while (fields.hasNext()) {
      String field = fields.next();
      if (!allowed.contains(field)) {
        throw new IllegalStateException(where + " has unknown field: " + field);
      }
    }
  }

  private static String withoutQuery(String path) {
    int query = path.indexOf('?');
    return query == -1 ? path : path.substring(0, query);
  }
}
