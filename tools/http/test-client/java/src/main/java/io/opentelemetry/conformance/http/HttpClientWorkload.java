/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import io.opentelemetry.conformance.http.HttpContract.Response;
import java.time.Duration;

/**
 * Shared support for JVM client scenarios: the request contract, sent by the library under test.
 *
 * <p>Only a <em>client</em> scenario needs this: it is the sender, so the requests have to leave
 * the library under test. A server scenario is driven from outside its own process by {@code
 * otel-http-drive} and never sends anything.
 *
 * <p>The shared telemetry contract checks what this request emits. The helper also verifies the
 * response against the selected contract entry.
 */
public final class HttpClientWorkload {

  /** Maximum time a client scenario waits for one request to finish. */
  public static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);

  private static final Duration INSTRUMENTATION_QUIESCENCE = Duration.ofMillis(100);

  private HttpClientWorkload() {}

  /** Sends one request using the HTTP client library under test. */
  @FunctionalInterface
  public interface Sender {
    /** {@code body} is null for a request that carries none. */
    Response send(String method, String url, String body) throws Exception;
  }

  /**
   * Sends the runner-selected contract request at {@code baseUrl} through {@code sender}.
   *
   * <p>No health check: the runner starts the mock server a client scenario calls and waits for it
   * to answer before running the scenario at all.
   */
  public static void drive(String baseUrl, Sender sender) throws Exception {
    drive(baseUrl, sender, HttpContract.scenarioRequest());
  }

  static void drive(String baseUrl, Sender sender, Exchange exchange) throws Exception {
    if (baseUrl.isBlank()) {
      throw new IllegalArgumentException("base URL must not be blank");
    }
    Response response = sender.send(exchange.method(), baseUrl + exchange.path(), exchange.body());
    System.out.printf(
        "%s %s -> %d %s%n",
        exchange.method(), exchange.path(), response.statusCode(), abbreviate(response.body()));
    HttpContract.verify(exchange, response);
    // Some asynchronous clients return the body before their instrumentation completion callback.
    Thread.sleep(INSTRUMENTATION_QUIESCENCE.toMillis());
  }

  private static String abbreviate(String value) {
    String singleLine = value.replace('\r', ' ').replace('\n', ' ');
    return singleLine.length() <= 60 ? singleLine : singleLine.substring(0, 60);
  }
}
