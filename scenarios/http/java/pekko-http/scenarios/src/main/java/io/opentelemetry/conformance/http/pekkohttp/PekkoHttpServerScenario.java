/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.pekkohttp;

import static org.apache.pekko.http.javadsl.server.PathMatchers.segment;

import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import org.apache.pekko.actor.ActorSystem;
import org.apache.pekko.http.javadsl.Http;
import org.apache.pekko.http.javadsl.ServerBinding;
import org.apache.pekko.http.javadsl.model.ContentTypes;
import org.apache.pekko.http.javadsl.model.HttpResponse;
import org.apache.pekko.http.javadsl.server.AllDirectives;
import org.apache.pekko.http.javadsl.server.Route;
import org.apache.pekko.http.javadsl.unmarshalling.Unmarshaller;

/**
 * Hosts the shared HTTP exchanges on Pekko HTTP's routing DSL until the driver says stop.
 *
 * <p>Pekko builds routes out of composed directives rather than declaring path templates, so the
 * segment matchers below are where an instrumentation reads a route from.
 */
public final class PekkoHttpServerScenario {
  private PekkoHttpServerScenario() {}

  public static void run() throws Exception {
    ActorSystem system = ActorSystem.create("http-conformance");
    try {
      ServerBinding binding =
          Http.get(system)
              .newServerAt("127.0.0.1", HttpServerWorkload.scenarioPort())
              .bind(new ConformanceRoutes().create())
              .toCompletableFuture()
              .get();

      try {
        ScenarioLifecycle.waitForEof();
      } finally {
        binding.unbind().toCompletableFuture().get();
      }
    } finally {
      system.terminate();
      system.getWhenTerminated().toCompletableFuture().get();
    }
  }

  /** The contract's exchanges, composed as Pekko HTTP directives. */
  private static final class ConformanceRoutes extends AllDirectives {
    Route create() {
      return concat(
          path("health", () -> get(() -> complete(answer("GET", "/health", null)))),
          pathPrefix(
              "users",
              () ->
                  path(
                      segment(),
                      userId -> get(() -> complete(answer("GET", "/users/" + userId, null))))),
          path(
              "items",
              () ->
                  post(
                      () ->
                          entity(
                              Unmarshaller.entityToString(),
                              body -> complete(answer("POST", "/items", body))))),
          pathPrefix(
              "status",
              () ->
                  path(
                      segment(),
                      code -> get(() -> complete(answer("GET", "/status/" + code, null))))));
    }
  }

  private static HttpResponse answer(String method, String path, String body) {
    Response answer =
        HttpServerWorkload.respond(method, path, body == null || body.isEmpty() ? null : body);
    return HttpResponse.create()
        .withStatus(answer.statusCode())
        .withEntity(ContentTypes.APPLICATION_JSON, answer.body());
  }
}
