/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebflux.SpringWebfluxServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.webflux.v5_3.SpringWebfluxServerTelemetry;
import org.springframework.web.server.WebFilter;

public final class SpringWebfluxLibraryServerScenario {
  private SpringWebfluxLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebfluxServerTelemetry telemetry =
          SpringWebfluxServerTelemetry.create(sdk.openTelemetry());
      WebFilter filter = telemetry.createWebFilterAndRegisterReactorHook();
      SpringWebfluxServerScenario.run(
          application ->
              application.addInitializers(
                  context ->
                      context
                          .getBeanFactory()
                          .registerSingleton("openTelemetryWebFilter", filter)));
    }
  }
}
