/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.vertxweb.VertxWebServerScenario;

public final class VertxWebJavaagentServerScenario {
  private VertxWebJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    VertxWebServerScenario.run();
  }
}
