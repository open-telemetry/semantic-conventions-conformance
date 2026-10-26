/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.netty.NettyServerScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.instrumentation.netty.v4_1.NettyServerTelemetry;

public final class NettyLibraryServerScenario {
  private NettyLibraryServerScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      NettyServerTelemetry telemetry = NettyServerTelemetry.create(sdk.openTelemetry());
      NettyServerScenario.run(pipeline -> pipeline.addLast(telemetry.createCombinedHandler()));
    }
  }
}
