/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.javahttpclient.JavaHttpClientClientScenario;

public final class JavaHttpClientJavaagentClientScenario {
  private JavaHttpClientJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    JavaHttpClientClientScenario.run();
  }
}
