/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebmvc.v5_3.SpringWebMvc5ServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.webmvc.v5_3.SpringWebMvcTelemetry;

public final class SpringWebMvc5LibraryServerScenario {
  private SpringWebMvc5LibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebMvc5ServerScenario.run(
          SpringWebMvcTelemetry.create(sdk.openTelemetry()).createServletFilter());
    }
  }
}
