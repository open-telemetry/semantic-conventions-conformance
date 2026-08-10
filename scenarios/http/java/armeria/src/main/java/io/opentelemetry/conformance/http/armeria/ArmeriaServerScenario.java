/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package io.opentelemetry.conformance.http.armeria;

import com.linecorp.armeria.common.HttpResponse;
import com.linecorp.armeria.common.HttpStatus;
import com.linecorp.armeria.common.MediaType;
import com.linecorp.armeria.server.Server;
import com.linecorp.armeria.server.ServerBuilder;
import io.opentelemetry.conformance.http.HttpTestClient;
import io.opentelemetry.instrumentation.armeria.v1_3.ArmeriaServerTelemetry;
import java.net.InetAddress;
import java.net.InetSocketAddress;

/** Hosts the shared route contract in Armeria and drives it with raw sockets. */
public final class ArmeriaServerScenario {
  private ArmeriaServerScenario() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      throw new IllegalArgumentException("usage: ArmeriaServerScenario <agent|library>");
    }

    try (ScenarioTelemetry telemetry = ScenarioTelemetry.initialize(args[0])) {
      InetAddress loopback = InetAddress.getByName("127.0.0.1");
      ServerBuilder builder =
          Server.builder()
              .http(new InetSocketAddress(loopback, 0))
              .service(
                  "/health",
                  (context, request) ->
                      HttpResponse.of(
                          HttpStatus.OK, MediaType.JSON_UTF_8, "{\"ok\":true}"))
              .service(
                  "/users/{userId}",
                  (context, request) ->
                      HttpResponse.of(
                          HttpStatus.OK,
                          MediaType.JSON_UTF_8,
                          "{\"id\":%s,\"name\":\"Alice\"}",
                          context.pathParam("userId")))
              .service(
                  "/items",
                  (context, request) ->
                      HttpResponse.of(
                          request
                              .aggregate()
                              .thenApply(
                                  aggregated ->
                                      HttpResponse.of(
                                          HttpStatus.CREATED,
                                          MediaType.JSON_UTF_8,
                                          "{\"created\":true,\"payload\":%s}",
                                          aggregated.contentUtf8()))))
              .service(
                  "/status/{code}",
                  (context, request) -> {
                    int code = Integer.parseInt(context.pathParam("code"));
                    String message =
                        code == 404
                            ? "not found"
                            : code == 500 ? "server error" : "ok";
                    return HttpResponse.of(
                        HttpStatus.valueOf(code),
                        MediaType.JSON_UTF_8,
                        "{\"message\":\"%s\"}",
                        message);
                  });

      if (telemetry.isLibrary()) {
        builder.decorator(
            ArmeriaServerTelemetry.create(telemetry.openTelemetry())
                .createDecorator());
      }

      Server server = builder.build();
      try {
        server.start().join();
        int port = server.activeLocalPort();
        HttpTestClient.drive(
            "http://" + loopback.getHostAddress() + ":" + port,
            HttpTestClient::rawRequest);
      } finally {
        server.stop().join();
      }
    }
  }
}
