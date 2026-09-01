/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * The HTTP conformance exchanges, as the JVM reads them.
 *
 * <p>Read from {@code otel-http-contract.yaml} on the classpath, which the build copies from {@code
 * tools/http/test-client/contract.yaml} — the one place it is written down, so a Java scenario and
 * a scenario in any other language are measured against the same traffic.
 *
 * <p>{@link #exchanges()} carries the concrete traffic and its answers. Every Java framework shares
 * this class rather than restating them, while server scenarios declare routes in their framework's
 * native form.
 */
public final class HttpContract {

  /** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
  public static final String CONTENT_TYPE = "application/json";

  /**
   * Fixed rather than the HTTP library's default, so a server scenario sees the same client
   * whichever language sent the requests.
   */
  public static final String USER_AGENT = "otel-http-conformance/1";

  public static final String SCENARIO_INDEX_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_INDEX";

  private static final String RESOURCE = "/otel-http-contract.yaml";

  private static final ObjectMapper YAML =
      new ObjectMapper(new YAMLFactory())
          .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
  private static final ObjectMapper JSON = new ObjectMapper();

  // Loaded on first use rather than in a static initializer, so a classpath problem arrives as the
  // message below rather than wrapped in ExceptionInInitializerError.
  private static volatile List<Exchange> requests;

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

  private record Request(String method, String path, String body) {}

  private record ExpectedResponse(int status, String body) {}

  private record Action(Request request, ExpectedResponse response) {}

  private record ContractDocument(String description, List<ScenarioEntry> scenarios) {}

  private record ScenarioEntry(String description, Action action) {
    Exchange exchange() {
      return new Exchange(
          action.request.method,
          action.request.path,
          action.request.body,
          action.response.status,
          action.response.body,
          false,
          description);
    }
  }

  private static final Exchange READINESS =
      new Exchange(
          "GET",
          "/health",
          null,
          200,
          "{\"ok\": true}",
          true,
          "Checks whether the server is ready.");

  /** Every exchange the contract describes, including readiness, in order. */
  public static List<Exchange> exchanges() {
    return java.util.stream.Stream.concat(
            java.util.stream.Stream.of(READINESS), requests().stream())
        .toList();
  }

  /** The measured requests to send, in order. */
  public static List<Exchange> requests() {
    List<Exchange> loaded = requests;
    if (loaded == null) {
      loaded = load();
      requests = loaded;
    }
    return loaded;
  }

  /** The one request selected by the runner's zero-based contract index. */
  public static Exchange scenarioRequest() {
    String raw = System.getenv(SCENARIO_INDEX_VARIABLE);
    if (raw == null || !raw.matches("0|[1-9][0-9]*")) {
      throw new IllegalStateException(
          SCENARIO_INDEX_VARIABLE + " must be a zero-based decimal index, got " + raw);
    }
    return request(Integer.parseInt(raw));
  }

  static Exchange request(int index) {
    if (index < 0 || index >= requests().size()) {
      throw new IllegalArgumentException(
          SCENARIO_INDEX_VARIABLE
              + "="
              + index
              + " selects no contract entry; expected 0.."
              + (requests().size() - 1));
    }
    return requests().get(index);
  }

  static void verify(Exchange exchange, Response response) {
    if (response.statusCode() != exchange.status()) {
      throw new IllegalStateException(
          exchange.method()
              + " "
              + exchange.path()
              + " answered "
              + response.statusCode()
              + ", expected "
              + exchange.status());
    }
    try {
      if (!JSON.readTree(exchange.renderResponseBody(exchange.body()))
          .equals(JSON.readTree(response.body()))) {
        throw new IllegalStateException(
            exchange.method() + " " + exchange.path() + " returned an unexpected JSON body");
      }
    } catch (IOException error) {
      throw new UncheckedIOException(
          exchange.method() + " " + exchange.path() + " did not return the expected JSON", error);
    }
  }

  /**
   * A status and a body: what a request came back as, and what a route answers.
   *
   * <p>One type for both directions, because they are the same pair — which is why the other
   * languages carry it as a plain tuple.
   */
  public record Response(int statusCode, String body) {}

  /** The exchange answering {@code method path}, if the contract describes one. */
  static Optional<Exchange> exchange(String method, String path) {
    String withoutQuery = withoutQuery(path);
    return exchanges().stream()
        .filter(exchange -> exchange.method().equals(method))
        .filter(exchange -> withoutQuery(exchange.path()).equals(withoutQuery))
        .findFirst();
  }

  private static String withoutQuery(String path) {
    int query = path.indexOf('?');
    return query == -1 ? path : path.substring(0, query);
  }

  private static List<Exchange> load() {
    try (InputStream stream = HttpContract.class.getResourceAsStream(RESOURCE)) {
      if (stream == null) {
        throw new IllegalStateException(
            RESOURCE
                + " is not on the classpath — the build copies it from"
                + " tools/http/test-client/contract.yaml");
      }
      return YAML.readValue(stream, ContractDocument.class).scenarios().stream()
          .map(ScenarioEntry::exchange)
          .collect(Collectors.toUnmodifiableList());
    } catch (IOException e) {
      throw new UncheckedIOException("could not read " + RESOURCE, e);
    }
  }
}
