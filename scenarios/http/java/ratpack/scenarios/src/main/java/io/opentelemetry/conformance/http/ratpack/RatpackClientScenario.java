/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.ratpack;

import io.opentelemetry.conformance.http.HttpClientWorkload;
import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.scenario.ScenarioEnvironment;
import java.net.InetAddress;
import java.net.URI;
import java.util.concurrent.CompletableFuture;
import ratpack.exec.ExecController;
import ratpack.exec.ExecInitializer;
import ratpack.exec.Promise;
import ratpack.func.Action;
import ratpack.http.client.HttpClient;
import ratpack.server.RatpackServer;
import ratpack.test.exec.ExecHarness;

/**
 * Runs the shared request contract through Ratpack's {@link HttpClient}.
 *
 * <p>Ratpack's client promises only resolve inside managed executions. Library instrumentation uses
 * a server-owned controller because its response interceptor runs in a child execution.
 */
public final class RatpackClientScenario {
  private RatpackClientScenario() {}

  public static void run() throws Exception {
    try (ExecHarness harness = ExecHarness.harness();
        HttpClient client = HttpClient.of(spec -> spec.execController(harness.getController()))) {
      HttpClientWorkload.drive(
          ScenarioEnvironment.require("MOCK_SERVER_URL"),
          (method, url, body) ->
              harness.yield(execution -> request(client, method, url, body)).getValueOrThrow());
    }
  }

  public static void run(ClientInstrumenter instrumenter, ExecInitializer execInitializer)
      throws Exception {
    RatpackServer server =
        RatpackServer.of(
            definition -> {
              definition.serverConfig(
                  config -> config.port(0).address(InetAddress.getByName("127.0.0.1")));
              definition.registryOf(registry -> registry.add(execInitializer));
              definition.handlers(chain -> {});
            });
    server.start();
    try {
      ExecController controller =
          server
              .getRegistry()
              .orElseThrow(() -> new IllegalStateException("Ratpack server did not start"))
              .get(ExecController.class);
      CompletableFuture<HttpClient> instrumentedClient = new CompletableFuture<>();
      controller
          .fork()
          .onError(instrumentedClient::completeExceptionally)
          .start(
              execution ->
                  instrumentedClient.complete(
                      instrumenter.instrument(HttpClient.of(Action.noop()))));
      try (HttpClient client = instrumentedClient.get()) {
        HttpClientWorkload.drive(
            ScenarioEnvironment.require("MOCK_SERVER_URL"),
            (method, url, body) -> request(controller, client, method, url, body));
      }
    } finally {
      server.stop();
    }
  }

  private static HttpContract.Response request(
      ExecController controller, HttpClient client, String method, String url, String body)
      throws Exception {
    CompletableFuture<HttpContract.Response> result = new CompletableFuture<>();
    controller
        .fork()
        .onError(result::completeExceptionally)
        .start(execution -> request(client, method, url, body).then(result::complete));
    return result.get();
  }

  private static Promise<HttpContract.Response> request(
      HttpClient client, String method, String url, String body) {
    return client
        .request(
            URI.create(url),
            request -> {
              request.method(method);
              request.headers(
                  headers -> {
                    headers.set("user-agent", HttpContract.USER_AGENT);
                    if (body != null) {
                      headers.set("content-type", HttpContract.CONTENT_TYPE);
                    }
                  });
              if (body != null) {
                request.body(content -> content.text(body));
              }
            })
        // Read inside the execution: the buffer backing the response is released as soon as it
        // ends.
        .map(
            response ->
                new HttpContract.Response(
                    response.getStatus().getCode(), response.getBody().getText()));
  }

  @FunctionalInterface
  public interface ClientInstrumenter {
    HttpClient instrument(HttpClient client) throws Exception;
  }
}
