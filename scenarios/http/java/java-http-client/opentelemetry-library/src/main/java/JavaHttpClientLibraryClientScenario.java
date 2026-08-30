/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.javahttpclient.JavaHttpClientClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.javahttpclient.JavaHttpClientTelemetry;
import java.net.http.HttpClient;

public final class JavaHttpClientLibraryClientScenario {
  private JavaHttpClientLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      JavaHttpClientTelemetry telemetry = JavaHttpClientTelemetry.create(sdk.openTelemetry());
      JavaHttpClientClientScenario.run(() -> telemetry.wrap(HttpClient.newBuilder().build()));
    }
  }
}
