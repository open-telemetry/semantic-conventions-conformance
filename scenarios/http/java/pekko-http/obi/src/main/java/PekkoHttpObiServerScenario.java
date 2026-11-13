/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.pekkohttp.PekkoHttpServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class PekkoHttpObiServerScenario {
  private PekkoHttpObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    PekkoHttpServerScenario.run();
  }
}
