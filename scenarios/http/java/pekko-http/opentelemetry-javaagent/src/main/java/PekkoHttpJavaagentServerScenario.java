/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.pekkohttp.PekkoHttpServerScenario;

public final class PekkoHttpJavaagentServerScenario {
  private PekkoHttpJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    PekkoHttpServerScenario.run();
  }
}
