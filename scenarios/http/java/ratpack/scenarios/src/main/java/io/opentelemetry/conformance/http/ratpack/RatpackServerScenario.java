/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.ratpack;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.net.InetAddress;
import java.util.function.Consumer;
import ratpack.handling.Context;
import ratpack.registry.RegistrySpec;
import ratpack.server.RatpackServer;

/** Hosts the shared HTTP exchanges on a Ratpack handler chain until the driver says stop. */
public final class RatpackServerScenario {
  private RatpackServerScenario() {}

  public static void run() throws Exception {
    run(registry -> {});
  }

  public static void run(Consumer<RegistrySpec> registryCustomizer) throws Exception {
    RatpackServer server =
        RatpackServer.of(
            definition -> {
              definition.serverConfig(
                  config ->
                      config
                          .port(HttpServerWorkload.scenarioPort())
                          .address(InetAddress.getByName("127.0.0.1")));
              definition.registryOf(registryCustomizer::accept);
              definition.handlers(
                  chain ->
                      chain
                          .get("health", context -> answer(context, null))
                          .get("users/:userId", context -> answer(context, null))
                          .post(
                              "items",
                              context ->
                                  context
                                      .getRequest()
                                      .getBody()
                                      .then(body -> answer(context, body.getText())))
                          .get("status/:code", context -> answer(context, null)));
            });

    server.start();
    try {
      ScenarioLifecycle.waitForEof();
    } finally {
      server.stop();
    }
  }

  private static void answer(Context context, String body) {
    Response answer =
        HttpServerWorkload.respond(
            context.getRequest().getMethod().getName(),
            // Ratpack reports the path without its leading slash.
            "/" + context.getRequest().getPath(),
            body == null || body.isEmpty() ? null : body);

    context
        .getResponse()
        .status(answer.statusCode())
        .send(HttpContract.CONTENT_TYPE, answer.body());
  }
}
