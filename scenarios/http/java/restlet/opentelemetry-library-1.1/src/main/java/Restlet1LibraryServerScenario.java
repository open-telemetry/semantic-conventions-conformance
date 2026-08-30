/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.restlet1.Restlet1ServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.restlet.v1_1.RestletTelemetry;
import org.restlet.Filter;

public final class Restlet1LibraryServerScenario {
  private Restlet1LibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      RestletTelemetry telemetry = RestletTelemetry.create(sdk.openTelemetry());
      Restlet1ServerScenario.run(
          (route, next) -> {
            Filter filter = telemetry.createFilter(route);
            filter.setNext(next);
            return filter;
          });
    }
  }
}
