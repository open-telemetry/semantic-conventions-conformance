/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.servlet.ServletServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class ServletObiServerScenario {
  private ServletObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    ServletServerScenario.run();
  }
}
