/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.springwebmvc.SpringWebMvcServerScenario;

public final class SpringWebMvcJavaagentServerScenario {
  private SpringWebMvcJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    SpringWebMvcServerScenario.run();
  }
}
