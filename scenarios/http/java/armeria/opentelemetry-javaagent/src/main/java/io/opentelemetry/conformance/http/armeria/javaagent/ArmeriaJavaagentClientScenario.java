/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria.javaagent;

import io.opentelemetry.conformance.http.armeria.ArmeriaClientScenario;

public final class ArmeriaJavaagentClientScenario {
  private ArmeriaJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    ArmeriaClientScenario.run();
  }
}
