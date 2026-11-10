/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** The scenario side of {@code otel-conformance-obi run}'s gate. */
public final class ScenarioGate {
  static final String GATE_VARIABLE = "OTEL_CONFORMANCE_GATE";
  private static final byte[] RELEASE = {'1'};

  private ScenarioGate() {}

  /**
   * Reads the named pipe in {@code OTEL_CONFORMANCE_GATE} until the launcher closes it, and fails
   * unless the launcher released the gate first. Returns at once when the variable is unset.
   */
  public static void waitAtGate() {
    waitAtGate(System.getenv(GATE_VARIABLE));
  }

  static void waitAtGate(String gate) {
    if (gate == null || gate.isEmpty()) {
      return;
    }
    InputStream pipe;
    try {
      pipe = Files.newInputStream(Path.of(gate));
    } catch (IOException error) {
      throw new IllegalStateException("reaching the gate: " + error.getMessage(), error);
    }
    byte[] received;
    try (pipe) {
      received = pipe.readAllBytes();
    } catch (IOException error) {
      throw new IllegalStateException("waiting at the gate: " + error.getMessage(), error);
    }
    if (!Arrays.equals(received, RELEASE)) {
      throw new IllegalStateException("the launcher closed the gate without releasing it");
    }
  }
}
