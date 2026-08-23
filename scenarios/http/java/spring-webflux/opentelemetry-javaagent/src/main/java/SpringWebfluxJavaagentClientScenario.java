/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebflux.SpringWebfluxClientScenario;

public final class SpringWebfluxJavaagentClientScenario {
  private SpringWebfluxJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    SpringWebfluxClientScenario.run();
  }
}
