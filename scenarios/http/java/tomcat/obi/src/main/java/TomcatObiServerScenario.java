/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.tomcat.TomcatServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class TomcatObiServerScenario {
  private TomcatObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    TomcatServerScenario.run();
  }
}
