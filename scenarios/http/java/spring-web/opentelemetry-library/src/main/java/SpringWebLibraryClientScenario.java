/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springweb.SpringWebClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.spring.web.v3_1.SpringWebTelemetry;

public final class SpringWebLibraryClientScenario {
  private SpringWebLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      SpringWebClientScenario.run(
          restTemplate ->
              restTemplate
                  .getInterceptors()
                  .add(SpringWebTelemetry.create(sdk.openTelemetry()).createInterceptor()));
    }
  }
}
