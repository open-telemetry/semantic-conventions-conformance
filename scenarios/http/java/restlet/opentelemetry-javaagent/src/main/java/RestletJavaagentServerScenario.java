/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.restlet.RestletServerScenario;

public final class RestletJavaagentServerScenario {
  private RestletJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    RestletServerScenario.run();
  }
}
