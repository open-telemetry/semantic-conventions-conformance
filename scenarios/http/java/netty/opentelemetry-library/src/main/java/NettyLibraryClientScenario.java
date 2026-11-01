/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.http.netty.NettyClientScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;
import io.opentelemetry.context.Context;
import io.opentelemetry.instrumentation.netty.v4_1.NettyClientTelemetry;

public final class NettyLibraryClientScenario {
  private NettyLibraryClientScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      NettyClientTelemetry telemetry = NettyClientTelemetry.create(sdk.openTelemetry());
      NettyClientScenario.run(
          pipeline -> pipeline.addLast(telemetry.createCombinedHandler()),
          channel -> NettyClientTelemetry.setParentContext(channel, Context.current()));
    }
  }
}
