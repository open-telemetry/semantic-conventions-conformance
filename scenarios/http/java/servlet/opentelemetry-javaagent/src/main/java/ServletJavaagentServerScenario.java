/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.servlet.ServletServerScenario;

public final class ServletJavaagentServerScenario {
  private ServletJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    ServletServerScenario.run();
  }
}
