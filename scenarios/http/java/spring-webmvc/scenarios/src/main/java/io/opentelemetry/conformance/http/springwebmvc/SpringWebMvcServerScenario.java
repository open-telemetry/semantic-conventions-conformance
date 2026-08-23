/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.springwebmvc;

import io.opentelemetry.conformance.http.HttpContract;
import io.opentelemetry.conformance.http.HttpContract.Response;
import io.opentelemetry.conformance.http.HttpServerWorkload;
import io.opentelemetry.conformance.scenario.ScenarioLifecycle;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * Hosts the shared HTTP exchanges on Spring Web MVC until the driver says stop.
 *
 * <p>The routes are request mappings, which is where an instrumentation reads {@code http.route}
 * from — the pattern rather than the concrete path.
 */
public final class SpringWebMvcServerScenario {
  private SpringWebMvcServerScenario() {}

  public static void run() throws Exception {
    SpringApplication application = new SpringApplication(ConformanceApplication.class);
    application.setDefaultProperties(
        Map.<String, Object>of(
            "server.address", "127.0.0.1", "server.port", HttpServerWorkload.scenarioPort()));

    try (ConfigurableApplicationContext context = application.run()) {
      ScenarioLifecycle.waitForEof();
    }
  }

  @SpringBootApplication
  static class ConformanceApplication {}

  /** The contract's exchanges, declared as Spring Web MVC request mappings. */
  @RestController
  static class ConformanceController {

    @GetMapping("/health")
    ResponseEntity<String> health(HttpServletRequest request) {
      return answer(request, null);
    }

    @GetMapping("/users/{userId}")
    ResponseEntity<String> getUser(HttpServletRequest request) {
      return answer(request, null);
    }

    @PostMapping("/items")
    ResponseEntity<String> createItem(
        HttpServletRequest request, @RequestBody(required = false) String body) {
      return answer(request, body);
    }

    @GetMapping("/status/{code}")
    ResponseEntity<String> status(HttpServletRequest request) {
      return answer(request, null);
    }

    private static ResponseEntity<String> answer(HttpServletRequest request, String body) {
      Response answer =
          HttpServerWorkload.respond(
              request.getMethod(),
              request.getRequestURI(),
              body == null || body.isEmpty() ? null : body);
      return ResponseEntity.status(answer.statusCode())
          .header("content-type", HttpContract.CONTENT_TYPE)
          .body(answer.body());
    }
  }
}
