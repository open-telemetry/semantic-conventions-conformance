/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.grizzly;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.nio.charset.StandardCharsets;
import org.glassfish.grizzly.http.server.HttpHandler;
import org.glassfish.grizzly.http.server.HttpServer;
import org.glassfish.grizzly.http.server.Request;

/** Hosts the shared HTTP exchanges on a Grizzly HTTP server until the driver says stop. */
public final class GrizzlyServerScenario {
  private GrizzlyServerScenario() {}

  public static void run() throws Exception {
    HttpServer server =
        HttpServer.createSimpleServer(null, "127.0.0.1", HttpServerWorkload.scenarioPort());
    server.getServerConfiguration().addHttpHandler(new ConformanceHandler(), "/health");
    server.getServerConfiguration().addHttpHandler(new ConformanceHandler(), "/users/*");
    server.getServerConfiguration().addHttpHandler(new ConformanceHandler(), "/items");
    server.getServerConfiguration().addHttpHandler(new ConformanceHandler(), "/status/*");

    server.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.shutdownNow();
    }
  }

  private static final class ConformanceHandler extends HttpHandler {
    @Override
    public void service(Request request, org.glassfish.grizzly.http.server.Response response)
        throws Exception {
      byte[] requestBody = request.getInputStream().readAllBytes();
      Response answer =
          HttpServerWorkload.respond(
              request.getMethod().getMethodString(),
              request.getRequestURI(),
              requestBody.length == 0 ? null : new String(requestBody, StandardCharsets.UTF_8));

      response.setStatus(answer.statusCode());
      response.setContentType(HttpContract.CONTENT_TYPE);
      response.getWriter().write(answer.body());
    }
  }
}
