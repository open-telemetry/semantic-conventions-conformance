/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.tomcat;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.apache.catalina.Context;
import org.apache.catalina.startup.Tomcat;

/**
 * Hosts the shared HTTP exchanges on embedded Tomcat until the driver says stop.
 *
 * <p>Tomcat routes through Servlet mappings, so {@code /users/*} and {@code /status/*} are what it
 * has in place of the contract's parameterized routes.
 */
public final class TomcatServerScenario {
  private TomcatServerScenario() {}

  public static void run() throws Exception {
    Tomcat tomcat = new Tomcat();
    tomcat.setHostname("127.0.0.1");
    tomcat.setPort(HttpServerWorkload.scenarioPort());
    tomcat.getConnector();

    Context context = tomcat.addContext("", System.getProperty("java.io.tmpdir"));
    mapServlet(context, "health", "/health");
    mapServlet(context, "users", "/users/*");
    mapServlet(context, "items", "/items");
    mapServlet(context, "status", "/status/*");

    tomcat.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      tomcat.stop();
      tomcat.destroy();
    }
  }

  private static void mapServlet(Context context, String name, String mapping) {
    Tomcat.addServlet(context, name, new ConformanceServlet());
    context.addServletMappingDecoded(mapping, name);
  }

  private static final class ConformanceServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;

    @Override
    protected void service(HttpServletRequest request, HttpServletResponse response)
        throws IOException {
      byte[] requestBody = request.getInputStream().readAllBytes();
      Response answer =
          HttpServerWorkload.respond(
              request.getMethod(),
              request.getRequestURI(),
              requestBody.length == 0 ? null : new String(requestBody, StandardCharsets.UTF_8));

      byte[] responseBody = answer.body().getBytes(StandardCharsets.UTF_8);
      response.setStatus(answer.statusCode());
      response.setContentType(HttpContract.CONTENT_TYPE);
      response.setContentLength(responseBody.length);
      response.getOutputStream().write(responseBody);
    }
  }
}
