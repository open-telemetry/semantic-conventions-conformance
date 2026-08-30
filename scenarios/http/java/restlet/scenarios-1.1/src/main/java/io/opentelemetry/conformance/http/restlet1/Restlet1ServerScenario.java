/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.restlet1;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.function.BiFunction;
import org.restlet.Component;
import org.restlet.Context;
import org.restlet.Restlet;
import org.restlet.Router;
import org.restlet.VirtualHost;
import org.restlet.data.MediaType;
import org.restlet.data.Protocol;
import org.restlet.data.Request;
import org.restlet.data.Response;
import org.restlet.data.Status;

/** Hosts the shared HTTP exchanges on Restlet 1 until the driver says stop. */
public final class Restlet1ServerScenario {
  private Restlet1ServerScenario() {}

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
      String requestBody = readEntity(request);
      HttpContract.Response answer =
          HttpServerWorkload.respond(
              request.getMethod().getName(),
              request.getResourceRef().getPath(),
              requestBody == null || requestBody.isEmpty() ? null : requestBody);

      response.setStatus(Status.valueOf(answer.statusCode()));
      response.setEntity(answer.body(), MediaType.APPLICATION_JSON);
    }

    private static String readEntity(Request request) {
      if (!request.isEntityAvailable()) {
        return null;
      }
      try {
        return request.getEntity().getText();
      } catch (IOException exception) {
        throw new UncheckedIOException(exception);
      }
    }
  }
}
