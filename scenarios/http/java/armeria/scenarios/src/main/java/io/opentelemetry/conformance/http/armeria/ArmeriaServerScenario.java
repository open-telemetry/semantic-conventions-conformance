/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria;

import com.linecorp.armeria.common.HttpMethod;
import com.linecorp.armeria.common.HttpResponse;
import com.linecorp.armeria.common.HttpStatus;
import com.linecorp.armeria.common.MediaType;
import com.linecorp.armeria.server.Server;
import com.linecorp.armeria.server.ServerBuilder;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.function.Consumer;

/**
 * Hosts the shared HTTP exchanges in Armeria until the driver says stop.
 *
 * <p>The routes are declared in Armeria's own API because an instrumentation reads {@code
 * http.route} from the framework's routing model. Other frameworks can declare the same exchanges
 * with annotations, compile-time routes, Servlet mappings, or their own runtime API. Answering is
 * an exact lookup of the concrete request and is therefore identical for every framework.
 *
 * <p>The requests are sent by {@code otel-http-drive} from another process, so nothing this JVM
 * loads can instrument the sender and record client spans in a server scenario's report. It listens
 * on the port the driver chose and shuts down when the driver closes its standard input, which is
 * what gives the SDK a chance to flush.
 */
public final class ArmeriaServerScenario {
  private ArmeriaServerScenario() {}

  /** Hosts them plainly, for a scenario whose instrumentation attaches itself. */
  public static void run() throws Exception {
    run(builder -> {});
  }

  public static void run(Consumer<ServerBuilder> configureServer) throws Exception {
    int port = HttpServerWorkload.scenarioPort();
    InetAddress loopback = InetAddress.getByName("127.0.0.1");
    ServerBuilder builder = Server.builder().http(new InetSocketAddress(loopback, port));

    registerRoute(builder, HttpMethod.GET, "/health");
    registerRoute(builder, HttpMethod.GET, "/users/{userId}");
    registerRoute(builder, HttpMethod.POST, "/items");
    registerRoute(builder, HttpMethod.GET, "/status/{code}");
    configureServer.accept(builder);

    Server server = builder.build();
    try {
      server.start().join();
      ScenarioLifecycle.waitForEof();
    } finally {
      server.stop().join();
    }
  }

  private static void registerRoute(ServerBuilder builder, HttpMethod method, String path) {
    builder
        .route()
        .methods(method)
        .path(path)
        .build(
            (context, request) ->
                HttpResponse.of(
                    request
                        .aggregate()
                        .thenApply(
                            aggregated -> {
                              Response answer =
                                  HttpServerWorkload.respond(
                                      aggregated.method().name(),
                                      context.path(),
                                      aggregated.contentUtf8());
                              return HttpResponse.of(
                                  HttpStatus.valueOf(answer.statusCode()),
                                  MediaType.parse(HttpContract.CONTENT_TYPE),
                                  answer.body());
                            })));
  }
}
