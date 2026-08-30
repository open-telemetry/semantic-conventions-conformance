/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebmvc.v6_0.SpringWebMvc6ServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.webmvc.v6_0.SpringWebMvcTelemetry;

public final class SpringWebMvc6LibraryServerScenario {
  private SpringWebMvc6LibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebMvc6ServerScenario.run(
          SpringWebMvcTelemetry.create(sdk.openTelemetry()).createServletFilter());
    }
  }
}
