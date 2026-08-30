/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.servlet3;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import javax.servlet.Filter;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.catalina.Context;
import org.apache.catalina.startup.Tomcat;
import org.apache.tomcat.util.descriptor.web.FilterDef;
import org.apache.tomcat.util.descriptor.web.FilterMap;

/** Hosts the shared HTTP exchanges in Servlet 3 until the driver says stop. */
public final class Servlet3ServerScenario {
  private Servlet3ServerScenario() {}

  public static void run(Filter telemetryFilter) throws Exception {
    Tomcat tomcat = new Tomcat();
    tomcat.setHostname("127.0.0.1");
    tomcat.setPort(HttpServerWorkload.scenarioPort());
    tomcat.getConnector();

    Context context = tomcat.addContext("", System.getProperty("java.io.tmpdir"));
    addFilter(context, telemetryFilter);
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

  private static void addFilter(Context context, Filter filter) {
    FilterDef definition = new FilterDef();
    definition.setFilterName("opentelemetry");
    definition.setFilter(filter);
    context.addFilterDef(definition);

    FilterMap mapping = new FilterMap();
    mapping.setFilterName("opentelemetry");
    mapping.addURLPattern("/*");
    context.addFilterMapBefore(mapping);
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
