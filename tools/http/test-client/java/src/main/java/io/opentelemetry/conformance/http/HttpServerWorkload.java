/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import io.opentelemetry.conformance.http.HttpContract.Response;
import java.util.List;

/**
 * Shared support for JVM server scenarios.
 *
 * <p>A server scenario declares routes with the framework under test — that declaration is what an
 * instrumentation reads {@code http.route} from — and then asks this class what to answer. Every
 * Java framework therefore agrees on the statuses and bodies without forcing its route construction
 * into a shared runtime model.
 *
 * <p>The requests are sent by {@code otel-http-drive} from another process, which checks each
 * answer against the same contract.
 */
public final class HttpServerWorkload {

  /**
   * The port a server scenario listens on. {@code otel-http-drive} chooses it, which is what lets
   * different scenarios run in parallel without colliding.
   */
  public static final String PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT";

  private HttpServerWorkload() {}

  /**
   * What the contract answers to one request.
   *
   * <p>The whole answer contract in one method, so every Java framework answers identically. {@code
   * requestBody} is null for a request that carried none.
   */
  public static Response respond(String method, String path, String requestBody) {
    return respond(method, path, requestBody, HttpContract.exchanges());
  }

  static Response respond(
      String method, String path, String requestBody, List<HttpContract.Exchange> exchanges) {
    return HttpContract.exchange(exchanges, method, path)
        .map(exchange -> new Response(exchange.status(), exchange.renderResponseBody(requestBody)))
        .orElseGet(() -> new Response(404, "{\"message\": \"no such route\"}"));
  }

  /** The port the driver told this scenario to listen on. */
  public static int scenarioPort() {
    String value = System.getenv(PORT_VARIABLE);
    if (value == null || value.isBlank()) {
      throw new IllegalStateException(
          PORT_VARIABLE
              + " is not set — a server scenario is started by `otel-http-drive`, which chooses"
              + " the port");
    }
    return Integer.parseInt(value);
  }
}
