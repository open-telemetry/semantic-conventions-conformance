/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.httpurlconnection.HttpUrlConnectionClientScenario;

public final class HttpUrlConnectionJavaagentClientScenario {
  private HttpUrlConnectionJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    HttpUrlConnectionClientScenario.run();
  }
}
