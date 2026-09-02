/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.restlet.RestletServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.restlet.v2_0.RestletTelemetry;
import org.restlet.routing.Filter;

public final class RestletLibraryServerScenario {
  private RestletLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      RestletTelemetry telemetry = RestletTelemetry.create(sdk.openTelemetry());
      RestletServerScenario.run(
          (route, next) -> {
            Filter filter = telemetry.createFilter(route);
            filter.setNext(next);
            return filter;
          });
    }
  }
}
