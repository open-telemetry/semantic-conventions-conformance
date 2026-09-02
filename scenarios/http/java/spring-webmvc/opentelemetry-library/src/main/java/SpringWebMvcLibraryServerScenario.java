/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebmvc.SpringWebMvcServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.webmvc.v6_0.SpringWebMvcTelemetry;

public final class SpringWebMvcLibraryServerScenario {
  private SpringWebMvcLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebMvcServerScenario.run(
          SpringWebMvcTelemetry.create(sdk.openTelemetry()).createServletFilter());
    }
  }
}
