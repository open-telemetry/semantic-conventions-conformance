/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria.javaagent;

import io.opentelemetry.conformance.http.armeria.ArmeriaServerScenario;

public final class ArmeriaJavaagentServerScenario {
  private ArmeriaJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    ArmeriaServerScenario.run();
  }
}
