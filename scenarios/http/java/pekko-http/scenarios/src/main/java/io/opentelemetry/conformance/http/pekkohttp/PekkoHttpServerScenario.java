/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.pekkohttp;

import static org.apache.pekko.http.javadsl.server.PathMatchers.segment;

import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.time.Duration;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
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
  /** How long the actor system gets to terminate before the scenario leaves without it. */
  private static final Duration TERMINATION_TIMEOUT = Duration.ofSeconds(10);

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
      terminate(system);
    }
    // Reached only once the scenario itself has finished, and deliberately: see terminate().
    System.exit(0);
  }

  /**
   * Ends the actor system, tolerating a termination that never finishes.
   *
   * <p>Pekko's shutdown has been seen to abort partway — its scheduler's close interrupted, the
   * {@code actor-system-terminate} phase reported as failed — which leaves non-daemon threads
   * behind. The JVM then never exits on its own, so the driver kills it 30s after closing standard
   * input and the agent's shutdown hook never runs. Metrics are exported only by that flush, which
   * makes such a run report every span and no metric at all: coverage the instrumentation looks to
   * have lost, rather than a scenario that failed to stop.
   *
   * <p>Neither the interruption nor the threads are this scenario's to fix, so the wait is bounded
   * and {@link #run} leaves through {@link System#exit} instead. That still runs the shutdown hook,
   * which is the part the report depends on.
   */
  private static void terminate(ActorSystem system) {
    system.terminate();
    try {
      system
          .getWhenTerminated()
          .toCompletableFuture()
          .get(TERMINATION_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    } catch (ExecutionException | TimeoutException e) {
      System.err.println("the actor system did not terminate cleanly: " + e);
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
