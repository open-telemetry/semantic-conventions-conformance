/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.javahttpserver.JavaHttpServerServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class JavaHttpServerObiServerScenario {
  private JavaHttpServerObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    JavaHttpServerServerScenario.run();
  }
}
