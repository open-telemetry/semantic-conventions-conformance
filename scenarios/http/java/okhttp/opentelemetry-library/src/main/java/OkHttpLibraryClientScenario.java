/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.okhttp.OkHttpClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.okhttp.v3_0.OkHttpTelemetry;
import okhttp3.OkHttpClient;

public final class OkHttpLibraryClientScenario {
  private OkHttpLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      OkHttpTelemetry telemetry = OkHttpTelemetry.create(sdk.openTelemetry());
      OkHttpClientScenario.run(telemetry.createCallFactory(new OkHttpClient()));
    }
  }
}
