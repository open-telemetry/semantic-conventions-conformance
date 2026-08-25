/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.asynchttpclient.AsyncHttpClientClientScenario;

public final class AsyncHttpClientJavaagentClientScenario {
  private AsyncHttpClientJavaagentClientScenario() {}

  public static void main(String[] args) throws Exception {
    AsyncHttpClientClientScenario.run();
  }
}
