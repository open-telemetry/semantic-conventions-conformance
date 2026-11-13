/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.armeria.ArmeriaServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class ArmeriaObiServerScenario {
  private ArmeriaObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    ArmeriaServerScenario.run();
  }
}
