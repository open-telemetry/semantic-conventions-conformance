/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.jaxrs.JaxRsServerScenario;

public final class JaxRsJavaagentServerScenario {
  private JaxRsJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    JaxRsServerScenario.run();
  }
}
