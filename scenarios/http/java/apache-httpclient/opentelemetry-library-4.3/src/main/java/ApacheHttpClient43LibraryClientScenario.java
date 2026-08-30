/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.apachehttpclient4.ApacheHttpClient4ClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.apachehttpclient.v4_3.ApacheHttpClientTelemetry;

public final class ApacheHttpClient43LibraryClientScenario {
  private ApacheHttpClient43LibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      ApacheHttpClientTelemetry telemetry = ApacheHttpClientTelemetry.create(sdk.openTelemetry());
      ApacheHttpClient4ClientScenario.run(telemetry::createHttpClient);
    }
  }
}
