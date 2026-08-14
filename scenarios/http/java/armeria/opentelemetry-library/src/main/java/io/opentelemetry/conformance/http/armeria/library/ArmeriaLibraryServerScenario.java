/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria.library;

import io.opentelemetry.conformance.http.armeria.ArmeriaServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.armeria.v1_3.ArmeriaServerTelemetry;

public final class ArmeriaLibraryServerScenario {
  private ArmeriaLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ArmeriaServerScenario.run(
          builder ->
              builder.decorator(
                  ArmeriaServerTelemetry.create(sdk.openTelemetry()).createDecorator()));
    }
  }
}
