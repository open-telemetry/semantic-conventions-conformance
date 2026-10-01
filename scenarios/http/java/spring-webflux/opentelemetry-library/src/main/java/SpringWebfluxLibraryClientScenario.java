/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebflux.SpringWebfluxClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.webflux.v5_3.SpringWebfluxClientTelemetry;

public final class SpringWebfluxLibraryClientScenario {
  private SpringWebfluxLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebfluxClientTelemetry telemetry =
          SpringWebfluxClientTelemetry.create(sdk.openTelemetry());
      SpringWebfluxClientScenario.run(
          builder -> builder.filters(telemetry::addFilterAndRegisterReactorHook));
    }
  }
}
