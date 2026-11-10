/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.undertow.UndertowServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class UndertowObiServerScenario {
  private UndertowObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    UndertowServerScenario.run();
  }
}
