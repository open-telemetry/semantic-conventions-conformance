/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.grizzly.GrizzlyServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class GrizzlyObiServerScenario {
  private GrizzlyObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    GrizzlyServerScenario.run();
  }
}
