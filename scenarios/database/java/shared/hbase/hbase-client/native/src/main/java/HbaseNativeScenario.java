/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import io.opentelemetry.conformance.database.hbase.HbaseScenario;
import io.opentelemetry.conformance.scenario.sdk.ScenarioSdk;

public final class HbaseNativeScenario {
  private HbaseNativeScenario() {}

  public static void main(String[] args) throws Exception {
    try (ScenarioSdk sdk = ScenarioSdk.initialize()) {
      HbaseScenario.main(args);
    }
  }
}
