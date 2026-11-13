/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.netty.NettyServerScenario;
import io.opentelemetry.conformance.scenario.ScenarioGate;

public final class NettyObiServerScenario {
  private NettyObiServerScenario() {}

  public static void main(String[] args) throws Exception {
    ScenarioGate.waitAtGate();
    NettyServerScenario.run();
  }
}
