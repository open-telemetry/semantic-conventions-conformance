/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.restlet;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.util.function.BiFunction;
import org.restlet.Component;
import org.restlet.Context;
import org.restlet.Request;
import org.restlet.Response;
import org.restlet.Restlet;
import org.restlet.data.MediaType;
import org.restlet.data.Protocol;
import org.restlet.data.Status;
import org.restlet.routing.Router;
import org.restlet.routing.VirtualHost;

/** Hosts the shared HTTP exchanges on a Restlet {@link Component} until the driver says stop. */
public final class RestletServerScenario {
  private RestletServerScenario() {}

  public static void run() throws Exception {
    run((route, restlet) -> restlet);
  }

  public static void run(BiFunction<String, Restlet, Restlet> instrumenter) throws Exception {
    Component component = new Component();
    component.getServers().add(Protocol.HTTP, "127.0.0.1", HttpServerWorkload.scenarioPort());

    VirtualHost host = component.getDefaultHost();
    Router router = new Router(host.getContext());
    router.attach(
        "/health", instrumenter.apply("/health", new ConformanceRestlet(host.getContext())));
    router.attach(
        "/users/{userId}",
        instrumenter.apply("/users/{userId}", new ConformanceRestlet(host.getContext())));
    router.attach(
        "/items", instrumenter.apply("/items", new ConformanceRestlet(host.getContext())));
    router.attach(
        "/status/{code}",
        instrumenter.apply("/status/{code}", new ConformanceRestlet(host.getContext())));
    host.attach(router);

    component.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      component.stop();
    }
  }

  private static final class ConformanceRestlet extends Restlet {
    ConformanceRestlet(Context context) {
      super(context);
    }

    @Override
    public void handle(Request request, Response response) {
      String requestBody = request.isEntityAvailable() ? request.getEntityAsText() : null;
      HttpContract.Response answer =
          HttpServerWorkload.respond(
              request.getMethod().getName(),
              request.getResourceRef().getPath(),
              requestBody == null || requestBody.isEmpty() ? null : requestBody);

      response.setStatus(Status.valueOf(answer.statusCode()));
      response.setEntity(answer.body(), MediaType.APPLICATION_JSON);
    }
  }
}
