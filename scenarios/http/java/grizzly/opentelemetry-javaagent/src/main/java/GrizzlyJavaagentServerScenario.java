/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.grizzly.GrizzlyServerScenario;

public final class GrizzlyJavaagentServerScenario {
  private GrizzlyJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    GrizzlyServerScenario.run();
  }
}
