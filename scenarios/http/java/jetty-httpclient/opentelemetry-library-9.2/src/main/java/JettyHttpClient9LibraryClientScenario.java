/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.jettyhttpclient9.JettyHttpClient9ClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.jetty.httpclient.v9_2.JettyClientTelemetry;

public final class JettyHttpClient9LibraryClientScenario {
  private JettyHttpClient9LibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      JettyClientTelemetry telemetry = JettyClientTelemetry.create(sdk.openTelemetry());
      JettyHttpClient9ClientScenario.run(telemetry::createHttpClient);
    }
  }
}
