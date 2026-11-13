/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebflux.SpringWebfluxServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class SpringWebfluxObiServerScenario {
  private SpringWebfluxObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    SpringWebfluxServerScenario.run();
  }
}
