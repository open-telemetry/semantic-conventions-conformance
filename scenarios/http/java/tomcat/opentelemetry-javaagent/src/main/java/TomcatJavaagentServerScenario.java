/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.tomcat.TomcatServerScenario;

public final class TomcatJavaagentServerScenario {
  private TomcatJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    TomcatServerScenario.run();
  }
}
