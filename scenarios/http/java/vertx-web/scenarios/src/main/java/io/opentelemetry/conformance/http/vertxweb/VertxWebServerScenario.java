/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.vertxweb;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import io.vertx.core.Vertx;
import io.vertx.ext.web.Router;
import io.vertx.ext.web.RoutingContext;
import io.vertx.ext.web.handler.BodyHandler;

/** Hosts the shared HTTP exchanges on a Vert.x Web {@link Router} until the driver says stop. */
public final class VertxWebServerScenario {
  private VertxWebServerScenario() {}

  public static void run() throws Exception {
    Vertx vertx = Vertx.vertx();
    Router router = Router.router(vertx);
    router.route().handler(BodyHandler.create());
    router.get("/health").handler(VertxWebServerScenario::answer);
    router.get("/users/:userId").handler(VertxWebServerScenario::answer);
    router.post("/items").handler(VertxWebServerScenario::answer);
    router.get("/status/:code").handler(VertxWebServerScenario::answer);

    io.vertx.core.http.HttpServer server =
        vertx
            .createHttpServer()
            .requestHandler(router)
            .listen(HttpServerWorkload.scenarioPort(), "127.0.0.1")
            .toCompletionStage()
            .toCompletableFuture()
            .get();

    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.close().toCompletionStage().toCompletableFuture().get();
      vertx.close().toCompletionStage().toCompletableFuture().get();
    }
  }

  private static void answer(RoutingContext context) {
    String requestBody = context.body().asString();
    Response answer =
        HttpServerWorkload.respond(
            context.request().method().name(), context.request().path(), requestBody);

    context
        .response()
        .setStatusCode(answer.statusCode())
        .putHeader("content-type", HttpContract.CONTENT_TYPE)
        .end(answer.body());
  }
}
