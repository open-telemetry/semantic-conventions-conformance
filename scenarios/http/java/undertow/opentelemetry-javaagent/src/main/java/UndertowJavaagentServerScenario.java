/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.undertow.UndertowServerScenario;

public final class UndertowJavaagentServerScenario {
  private UndertowJavaagentServerScenario() {}

  public static void main(String[] args) throws Exception {
    UndertowServerScenario.run();
  }
}
