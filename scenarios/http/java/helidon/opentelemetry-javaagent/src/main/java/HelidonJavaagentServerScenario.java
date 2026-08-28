/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.helidon.HelidonServerScenario;

public final class HelidonJavaagentServerScenario {
  private HelidonJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    HelidonServerScenario.run();
  }
}
