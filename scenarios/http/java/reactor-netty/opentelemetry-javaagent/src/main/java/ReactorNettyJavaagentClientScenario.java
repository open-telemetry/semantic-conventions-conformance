/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.reactornetty.ReactorNettyClientScenario;

public final class ReactorNettyJavaagentClientScenario {
  private ReactorNettyJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    ReactorNettyClientScenario.run();
  }
}
