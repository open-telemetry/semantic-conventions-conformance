/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.helidon;

import io.helidon.http.HeaderNames;
import io.helidon.http.Status;
import io.helidon.webserver.WebServer;
import io.helidon.webserver.http.HttpRouting;
import io.helidon.webserver.http.ServerRequest;
import io.helidon.webserver.http.ServerResponse;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.util.function.Consumer;

/** Hosts the shared HTTP exchanges on a Helidon {@link WebServer} until the driver says stop. */
public final class HelidonServerScenario {
  private HelidonServerScenario() {}

  public static void run() throws Exception {
    run(builder -> {});
  }

  public static void run(Consumer<HttpRouting.Builder> routingCustomizer) throws Exception {
    HttpRouting.Builder routing =
        HttpRouting.builder()
            .get("/health", HelidonServerScenario::answer)
            .get("/users/{userId}", HelidonServerScenario::answer)
            .post("/items", HelidonServerScenario::answer)
            .get("/status/{code}", HelidonServerScenario::answer);
    routingCustomizer.accept(routing);

    WebServer server =
        WebServer.builder()
            .host("127.0.0.1")
            .port(HttpServerWorkload.scenarioPort())
            .routing(routing)
            .build()
            .start();

    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.stop();
    }
  }

  private static void answer(ServerRequest request, ServerResponse response) {
    String requestBody = request.content().hasEntity() ? request.content().as(String.class) : null;
    Response answer =
        HttpServerWorkload.respond(
            request.prologue().method().text(), request.path().path(), requestBody);

    response.status(Status.create(answer.statusCode()));
    response.header(HeaderNames.CONTENT_TYPE, HttpContract.CONTENT_TYPE);
    response.send(answer.body());
  }
}
