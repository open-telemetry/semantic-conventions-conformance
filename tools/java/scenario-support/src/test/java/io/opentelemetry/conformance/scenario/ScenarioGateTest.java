/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ScenarioGateTest {
  @TempDir Path directory;

  @Test
  void theGateIsNamedByTheLaunchersVariable() {
    assertEquals("OTEL_CONFORMANCE_GATE", ScenarioGate.GATE_VARIABLE);
  }

  @Test
  void noGateReturnsAtOnce() {
    ScenarioGate.waitAtGate((String) null);
    ScenarioGate.waitAtGate("");
  }

  @Test
  void releasedGateLetsTheScenarioRun() throws Exception {
    ScenarioGate.waitAtGate(gateHolding(new byte[] {'1'}));
  }

  @Test
  void gateClosedWithoutReleaseFails() throws Exception {
    assertEquals("the launcher closed the gate without releasing it", failure(new byte[0]));
  }

  @Test
  void anythingButTheReleaseFails() throws Exception {
    assertEquals("the launcher closed the gate without releasing it", failure(new byte[] {'0'}));
    assertEquals(
        "the launcher closed the gate without releasing it", failure(new byte[] {'1', '1'}));
  }

  @Test
  void unreachableGateFails() {
    IllegalStateException error =
        assertThrows(
            IllegalStateException.class,
            () -> ScenarioGate.waitAtGate(directory.resolve("missing").toString()));
    assertTrue(error.getMessage().startsWith("reaching the gate: "), error.getMessage());
  }

  private String failure(byte[] written) throws Exception {
    String gate = gateHolding(written);
    return assertThrows(IllegalStateException.class, () -> ScenarioGate.waitAtGate(gate))
        .getMessage();
  }

  private String gateHolding(byte[] written) throws Exception {
    Path gate = Files.createTempFile(directory, "gate", "");
    Files.write(gate, written);
    return gate.toString();
  }
}
