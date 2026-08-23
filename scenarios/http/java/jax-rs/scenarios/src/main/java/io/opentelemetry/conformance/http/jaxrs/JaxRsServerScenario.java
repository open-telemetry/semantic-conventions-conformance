/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.jaxrs;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.UriInfo;
import org.apache.catalina.startup.Tomcat;
import org.glassfish.jersey.server.ResourceConfig;
import org.glassfish.jersey.servlet.ServletContainer;

/**
 * Hosts the shared HTTP exchanges on JAX-RS resource methods until the driver says stop.
 *
 * <p>The routes are {@code @Path} annotations, which is where a JAX-RS instrumentation reads {@code
 * http.route} from. Jersey runs the resource, and Tomcat hosts the servlet container.
 */
public final class JaxRsServerScenario {
  private JaxRsServerScenario() {}

  public static void run() throws Exception {
    Tomcat tomcat = new Tomcat();
    tomcat.setHostname("127.0.0.1");
    tomcat.setPort(HttpServerWorkload.scenarioPort());
    tomcat.getConnector();

    org.apache.catalina.Context context =
        tomcat.addContext("", System.getProperty("java.io.tmpdir"));
    Tomcat.addServlet(
        context, "jersey", new ServletContainer(new ResourceConfig(ConformanceResource.class)));
    context.addServletMappingDecoded("/*", "jersey");

    tomcat.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      tomcat.stop();
      tomcat.destroy();
    }
  }

  /** The contract's exchanges, declared as JAX-RS resource methods. */
  @Path("/")
  public static final class ConformanceResource {

    @Context private UriInfo uriInfo;

    @GET
    @Path("health")
    public Response health() {
      return answer("GET", null);
    }

    @GET
    @Path("users/{userId}")
    public Response getUser() {
      return answer("GET", null);
    }

    @POST
    @Path("items")
    public Response createItem(String body) {
      return answer("POST", body);
    }

    @GET
    @Path("status/{code}")
    public Response status() {
      return answer("GET", null);
    }

    private Response answer(String method, String body) {
      HttpContract.Response answer =
          HttpServerWorkload.respond(
              method, "/" + uriInfo.getPath(), body == null || body.isEmpty() ? null : body);
      return Response.status(answer.statusCode())
          .type(HttpContract.CONTENT_TYPE)
          .entity(answer.body())
          .build();
    }
  }
}
