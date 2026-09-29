/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.ratpack.RatpackClientScenario;

public final class RatpackJavaagentClientScenario {
  private RatpackJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    RatpackClientScenario.run();
  }
}
