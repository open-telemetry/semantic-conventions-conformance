/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.springwebflux;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import java.util.Map;
import java.util.function.Consumer;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.http.ResponseEntity;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

/**
 * Hosts the shared HTTP exchanges on Spring WebFlux until the driver says stop.
 *
 * <p>The routes are request mappings, which is where an instrumentation reads {@code http.route}
 * from — the pattern rather than the concrete path.
 */
public final class SpringWebfluxServerScenario {
  private SpringWebfluxServerScenario() {}

  public static void run() throws Exception {
    run(application -> {});
  }

  public static void run(Consumer<SpringApplication> applicationCustomizer) throws Exception {
    SpringApplication application = new SpringApplication(ConformanceApplication.class);
    applicationCustomizer.accept(application);
    application.setDefaultProperties(
        Map.<String, Object>of(
            "server.address", "127.0.0.1", "server.port", HttpServerWorkload.scenarioPort()));

    try (ConfigurableApplicationContext context = application.run()) {
      ScenarioLifecycle.waitForEof();
    }
  }

  @SpringBootApplication
  static class ConformanceApplication {}

  /** The contract's exchanges, declared as Spring WebFlux request mappings. */
  @RestController
  static class ConformanceController {

    @GetMapping("/health")
    Mono<ResponseEntity<String>> health(ServerHttpRequest request) {
      return answer(request, null);
    }

    @GetMapping("/users/{userId}")
    Mono<ResponseEntity<String>> getUser(ServerHttpRequest request) {
      return answer(request, null);
    }

    @PostMapping("/items")
    Mono<ResponseEntity<String>> createItem(
        ServerHttpRequest request, @RequestBody(required = false) String body) {
      return answer(request, body);
    }

    @GetMapping("/status/{code}")
    Mono<ResponseEntity<String>> status(ServerHttpRequest request) {
      return answer(request, null);
    }

    private static Mono<ResponseEntity<String>> answer(ServerHttpRequest request, String body) {
      Response answer =
          HttpServerWorkload.respond(
              request.getMethod().name(),
              request.getPath().value(),
              body == null || body.isEmpty() ? null : body);
      return Mono.just(
          ResponseEntity.status(answer.statusCode())
              .header("content-type", HttpContract.CONTENT_TYPE)
              .body(answer.body()));
    }
  }
}
