/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.apachehttpclient.ApacheHttpClientClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.apachehttpclient.v5_2.ApacheHttpClientTelemetry;

public final class ApacheHttpClientLibraryClientScenario {
  private ApacheHttpClientLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ApacheHttpClientTelemetry telemetry = ApacheHttpClientTelemetry.create(sdk.openTelemetry());
      ApacheHttpClientClientScenario.run(telemetry::createHttpClient);
    }
  }
}
