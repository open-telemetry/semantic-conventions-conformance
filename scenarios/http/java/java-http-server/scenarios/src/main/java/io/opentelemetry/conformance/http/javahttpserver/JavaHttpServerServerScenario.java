/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.javahttpserver;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/** Hosts the shared HTTP exchanges in the JDK's {@link HttpServer} until the driver says stop. */
public final class JavaHttpServerServerScenario {
  private JavaHttpServerServerScenario() {}

  public static void run() throws Exception {
    InetAddress loopback = InetAddress.getByName("127.0.0.1");
    HttpServer server =
        HttpServer.create(new InetSocketAddress(loopback, HttpServerWorkload.scenarioPort()), 0);

    server.createContext("/", JavaHttpServerServerScenario::answer);

    server.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.stop(0);
    }
  }

  private static void answer(HttpExchange exchange) throws IOException {
    byte[] requestBody = exchange.getRequestBody().readAllBytes();
    Response answer =
        HttpServerWorkload.respond(
            exchange.getRequestMethod(),
            exchange.getRequestURI().getPath(),
            requestBody.length == 0 ? null : new String(requestBody, StandardCharsets.UTF_8));

    byte[] responseBody = answer.body().getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().set("Content-Type", HttpContract.CONTENT_TYPE);
    exchange.sendResponseHeaders(answer.statusCode(), responseBody.length);
    try (OutputStream output = exchange.getResponseBody()) {
      output.write(responseBody);
    }
  }
}
