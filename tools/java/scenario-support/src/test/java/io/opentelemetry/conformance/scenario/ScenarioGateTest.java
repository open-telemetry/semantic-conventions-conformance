/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.DisabledOnOs;
import org.junit.jupiter.api.condition.OS;
import org.junit.jupiter.api.io.TempDir;

class ScenarioGateTest {
  private static final long TIMEOUT_SECONDS = 10;

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
  @DisabledOnOs(OS.WINDOWS)
  void releasedGateLetsTheScenarioRun() throws Exception {
    Path gate = fifo();
    Scenario scenario = new Scenario(gate);
    Launcher launcher = new Launcher(gate, new byte[] {'1'});
    assertTrue(launcher.holding.await(TIMEOUT_SECONDS, TimeUnit.SECONDS));
    assertFalse(scenario.done.await(200, TimeUnit.MILLISECONDS), "the scenario passed a held gate");
    launcher.release.countDown();
    assertTrue(scenario.done.await(TIMEOUT_SECONDS, TimeUnit.SECONDS));
    assertNull(scenario.failure.get(), () -> String.valueOf(scenario.failure.get()));
    launcher.finish();
  }

  @Test
  @DisabledOnOs(OS.WINDOWS)
  void gateClosedWithoutReleaseFails() throws Exception {
    assertEquals("the launcher closed the gate without releasing it", closedWith(new byte[0]));
  }

  @Test
  @DisabledOnOs(OS.WINDOWS)
  void anythingButTheReleaseFails() throws Exception {
    assertEquals("the launcher closed the gate without releasing it", closedWith(new byte[] {'0'}));
    assertEquals(
        "the launcher closed the gate without releasing it", closedWith(new byte[] {'1', '1'}));
  }

  @Test
  void unreachableGateFails() {
    IllegalStateException error =
        assertThrows(
            IllegalStateException.class,
            () -> ScenarioGate.waitAtGate(directory.resolve("missing").toString()));
    assertTrue(error.getMessage().startsWith("reaching the gate: "), error.getMessage());
  }

  private String closedWith(byte[] written) throws Exception {
    Path gate = fifo();
    Scenario scenario = new Scenario(gate);
    Launcher launcher = new Launcher(gate, written);
    launcher.release.countDown();
    assertTrue(scenario.done.await(TIMEOUT_SECONDS, TimeUnit.SECONDS));
    launcher.finish();
    Throwable failure = scenario.failure.get();
    assertTrue(failure instanceof IllegalStateException, () -> String.valueOf(failure));
    return failure.getMessage();
  }

  private Path fifo() throws Exception {
    Path gate = Files.createTempDirectory(directory, "gate").resolve("gate");
    Process mkfifo = new ProcessBuilder("mkfifo", gate.toString()).inheritIO().start();
    assertTrue(mkfifo.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS));
    assertEquals(0, mkfifo.exitValue());
    return gate;
  }

  private static final class Scenario {
    final CountDownLatch done = new CountDownLatch(1);
    final AtomicReference<Throwable> failure = new AtomicReference<>();

    Scenario(Path gate) {
      Thread thread =
          new Thread(
              () -> {
                try {
                  ScenarioGate.waitAtGate(gate.toString());
                } catch (Throwable error) {
                  failure.set(error);
                } finally {
                  done.countDown();
                }
              },
              "scenario");
      thread.setDaemon(true);
      thread.start();
    }
  }

  private static final class Launcher {
    final CountDownLatch holding = new CountDownLatch(1);
    final CountDownLatch release = new CountDownLatch(1);
    private final AtomicReference<Throwable> failure = new AtomicReference<>();
    private final Thread thread;

    Launcher(Path gate, byte[] written) {
      thread =
          new Thread(
              () -> {
                try (OutputStream pipe = Files.newOutputStream(gate)) {
                  holding.countDown();
                  if (!release.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                    throw new IllegalStateException("the test never released the launcher");
                  }
                  pipe.write(written);
                } catch (Throwable error) {
                  failure.set(error);
                }
              },
              "launcher");
      thread.setDaemon(true);
      thread.start();
    }

    void finish() throws InterruptedException {
      thread.join(TimeUnit.SECONDS.toMillis(TIMEOUT_SECONDS));
      assertFalse(thread.isAlive(), "the launcher is still holding the gate");
      assertNull(failure.get(), () -> String.valueOf(failure.get()));
    }
  }
}
