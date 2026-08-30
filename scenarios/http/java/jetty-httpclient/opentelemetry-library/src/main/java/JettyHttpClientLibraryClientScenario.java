/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.jettyhttpclient.JettyHttpClientClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.jetty.httpclient.v12_0.JettyClientTelemetry;

public final class JettyHttpClientLibraryClientScenario {
  private JettyHttpClientLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      JettyClientTelemetry telemetry = JettyClientTelemetry.create(sdk.openTelemetry());
      JettyHttpClientClientScenario.run(telemetry::createHttpClient);
    }
  }
}
