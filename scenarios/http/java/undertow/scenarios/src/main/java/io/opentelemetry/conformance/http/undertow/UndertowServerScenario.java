/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.undertow;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import io.undertow.Handlers;
import io.undertow.Undertow;
import io.undertow.server.HttpServerExchange;
import io.undertow.server.handlers.BlockingHandler;
import io.undertow.server.handlers.PathTemplateHandler;
import io.undertow.util.Headers;
import java.nio.charset.StandardCharsets;

/** Hosts the shared HTTP exchanges on Undertow's path templates until the driver says stop. */
public final class UndertowServerScenario {
  private UndertowServerScenario() {}

  public static void run() throws Exception {
    PathTemplateHandler routes = Handlers.pathTemplate();
    routes.add("/health", UndertowServerScenario::answer);
    routes.add("/users/{userId}", UndertowServerScenario::answer);
    routes.add("/items", UndertowServerScenario::answer);
    routes.add("/status/{code}", UndertowServerScenario::answer);

    Undertow server =
        Undertow.builder()
            .addHttpListener(HttpServerWorkload.scenarioPort(), "127.0.0.1")
            // Blocking, so a handler can read the request body it has to echo.
            .setHandler(new BlockingHandler(routes))
            .build();

    server.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.stop();
    }
  }

  private static void answer(HttpServerExchange exchange) throws Exception {
    byte[] requestBody = exchange.getInputStream().readAllBytes();
    Response answer =
        HttpServerWorkload.respond(
            exchange.getRequestMethod().toString(),
            exchange.getRequestPath(),
            requestBody.length == 0 ? null : new String(requestBody, StandardCharsets.UTF_8));

    exchange.setStatusCode(answer.statusCode());
    exchange.getResponseHeaders().put(Headers.CONTENT_TYPE, HttpContract.CONTENT_TYPE);
    exchange.getResponseSender().send(answer.body());
  }
}
