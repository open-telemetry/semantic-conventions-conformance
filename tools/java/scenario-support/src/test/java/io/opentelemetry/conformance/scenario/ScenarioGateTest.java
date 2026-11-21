/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.condition.EnabledOnOs;
import org.junit.jupiter.api.condition.OS;
import org.junit.jupiter.api.io.TempDir;

class ScenarioGateTest {
  @TempDir Path directory;

  @Test
  void noGateReturnsAtOnce() {
    ScenarioGate.waitAtGate(null);
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

  @Test
  @EnabledOnOs(OS.LINUX)
  @Timeout(value = 30, unit = TimeUnit.SECONDS)
  void releasedNamedPipeLetsTheScenarioRun() throws Exception {
    Path gate = namedPipe();
    CompletableFuture<Void> launcher = writeLater(gate, new byte[] {'1'});
    ScenarioGate.waitAtGate(gate.toString());
    launcher.get();
  }

  @Test
  @EnabledOnOs(OS.LINUX)
  @Timeout(value = 30, unit = TimeUnit.SECONDS)
  void namedPipeClosedWithoutReleaseFails() throws Exception {
    Path gate = namedPipe();
    CompletableFuture<Void> launcher = writeLater(gate, new byte[0]);
    IllegalStateException error =
        assertThrows(IllegalStateException.class, () -> ScenarioGate.waitAtGate(gate.toString()));
    assertEquals("the launcher closed the gate without releasing it", error.getMessage());
    launcher.get();
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

  private Path namedPipe() throws Exception {
    Path gate = directory.resolve("gate");
    Process mkfifo = new ProcessBuilder("mkfifo", gate.toString()).inheritIO().start();
    assertEquals(0, mkfifo.waitFor());
    return gate;
  }

  private static CompletableFuture<Void> writeLater(Path gate, byte[] written) {
    return CompletableFuture.runAsync(
        () -> {
          try (OutputStream pipe = Files.newOutputStream(gate)) {
            Thread.sleep(200);
            pipe.write(written);
          } catch (Exception error) {
            throw new IllegalStateException(error);
          }
        },
        command -> new Thread(command).start());
  }
}
