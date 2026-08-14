/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http.armeria.library;

import com.linecorp.armeria.client.WebClient;
import io.opentelemetry.conformance.http.armeria.ArmeriaClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.armeria.v1_3.ArmeriaClientTelemetry;

public final class ArmeriaLibraryClientScenario {
  private ArmeriaLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ArmeriaClientScenario.run(
          baseUrl ->
              WebClient.builder(baseUrl)
                  .decorator(ArmeriaClientTelemetry.create(sdk.openTelemetry()).createDecorator())
                  .build());
    }
  }
}
