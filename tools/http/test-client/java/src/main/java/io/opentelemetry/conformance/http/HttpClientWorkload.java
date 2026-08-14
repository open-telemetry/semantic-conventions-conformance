/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import com.fasterxml.jackson.databind.JsonNode;
import io.opentelemetry.conformance.http.HttpContract.Exchange;
import io.opentelemetry.conformance.http.HttpContract.Response;
import org.jspecify.annotations.Nullable;

/**
 * Shared support for JVM client scenarios: the request contract, sent by the library under test.
 *
 * <p>Only a <em>client</em> scenario needs this: it is the sender, so the requests have to leave
 * the library under test. A server scenario is driven from outside its own process by {@code
 * otel-http-drive} and never sends anything.
 *
 * <p>Every answer is checked against its exchange, so a server answering different traffic from the
 * rest fails the run rather than quietly producing a coverage file that cannot be compared with the
 * others.
 */
public final class HttpClientWorkload {

  private HttpClientWorkload() {}

  /** Sends one request using the HTTP client library under test. */
  @FunctionalInterface
  public interface Sender {
    Response send(String method, String url, @Nullable String body) throws Exception;
  }

  /**
   * Sends {@link HttpContract#requests()} at {@code baseUrl} through {@code sender}.
   *
   * <p>No health check: the runner starts the mock server a client scenario calls and waits for it
   * to answer before running the scenario at all.
   */
  public static void drive(String baseUrl, Sender sender) throws Exception {
    if (baseUrl.isBlank()) {
      throw new IllegalArgumentException("base URL must not be blank");
    }
    for (Exchange exchange : HttpContract.requests()) {
      Response response =
          sender.send(exchange.method(), baseUrl + exchange.path(), exchange.body());
      System.out.printf(
          "%s %s -> %d %s%n",
          exchange.method(), exchange.path(), response.statusCode(), abbreviate(response.body()));
      verify(exchange, response);
    }
  }

  /** Checks one answer against the exchange that describes it. */
  public static void verify(Exchange exchange, Response response) {
    if (response.statusCode() != exchange.status()) {
      throw new ContractError(
          exchange.method()
              + " "
              + exchange.path()
              + " answered "
              + response.statusCode()
              + ", but the contract's request"
              + " answers "
              + exchange.status());
    }

    // Parsed, not compared as text: whitespace and key order are a language's choice of JSON
    // writer, and neither is part of the contract.
    JsonNode expectedBody = HttpContract.parse(exchange.renderResponseBody(exchange.body()));
    JsonNode actualBody = HttpContract.parse(response.body());
    if (!expectedBody.equals(actualBody)) {
      throw new ContractError(
          exchange.method()
              + " "
              + exchange.path()
              + " answered "
              + actualBody
              + ", but the contract's request"
              + " answers "
              + expectedBody);
    }
  }

  private static String abbreviate(String value) {
    String singleLine = value.replace('\r', ' ').replace('\n', ' ');
    return singleLine.length() <= 60 ? singleLine : singleLine.substring(0, 60);
  }
}
