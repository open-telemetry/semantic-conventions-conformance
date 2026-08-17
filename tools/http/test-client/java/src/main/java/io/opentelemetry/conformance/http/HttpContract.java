/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.List;
import java.util.Optional;

/**
 * The HTTP conformance exchanges, as the JVM reads them.
 *
 * <p>Read from {@code otel-http-contract.json} on the classpath, which the build copies from {@code
 * tools/http/test-client/contract.json} — the one place it is written down, so a Java scenario and
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

  private static final String RESOURCE = "/otel-http-contract.json";

  private static final ObjectMapper MAPPER =
      new ObjectMapper().disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

  // Loaded on first use rather than in a static initializer, so a classpath problem arrives as the
  // message below rather than wrapped in ExceptionInInitializerError.
  private static volatile Document document;

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

  /** Every exchange the contract describes, including readiness, in order. */
  public static List<Exchange> exchanges() {
    return document().requests();
  }

  /** The measured requests to send, in order. */
  public static List<Exchange> requests() {
    return exchanges().stream().filter(exchange -> !exchange.readiness()).toList();
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

  /**
   * Parses {@code json}, so two bodies compare by structure rather than by spacing.
   *
   * <p>Package-private: Jackson is how this module reads the contract, not something a scenario has
   * to depend on.
   */
  static JsonNode parse(String json) {
    JsonNode parsed;
    try {
      parsed = MAPPER.readTree(json);
    } catch (IOException e) {
      throw new ContractError("not JSON: " + json, e);
    }
    // An empty or blank body parses to a missing node rather than failing, which would otherwise
    // surface as a confusing comparison instead of "this is not JSON".
    if (parsed == null || parsed.isMissingNode()) {
      throw new ContractError("not JSON: " + json);
    }
    return parsed;
  }

  private record Document(List<Exchange> requests) {
    Document {
      requests = List.copyOf(requests);
    }
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
    try (InputStream stream = HttpContract.class.getResourceAsStream(RESOURCE)) {
      if (stream == null) {
        throw new IllegalStateException(
            RESOURCE
                + " is not on the classpath — the build copies it from"
                + " tools/http/test-client/contract.json");
      }
      return MAPPER.readValue(stream, Document.class);
    } catch (IOException e) {
      throw new UncheckedIOException("could not read " + RESOURCE, e);
    }
  }
}
