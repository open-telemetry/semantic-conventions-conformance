/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.jettyhttpclient.JettyHttpClientClientScenario;

public final class JettyHttpClientJavaagentClientScenario {
  private JettyHttpClientJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    JettyHttpClientClientScenario.run();
  }
}
