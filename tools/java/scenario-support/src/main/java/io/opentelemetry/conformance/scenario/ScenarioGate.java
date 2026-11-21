/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** The scenario side of {@code otel-conformance-obi run}'s gate. */
final class ScenarioGate {
  static final String GATE_VARIABLE = "OTEL_CONFORMANCE_GATE";
  private static final byte[] RELEASE = {'1'};

  private ScenarioGate() {}

  /**
   * Reads the named pipe at {@code gate} until the launcher closes it, and fails unless the
   * launcher released the gate first. Returns at once when there is no gate.
   */
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
    ByteArrayOutputStream received = new ByteArrayOutputStream();
    try (pipe) {
      byte[] buffer = new byte[8];
      for (int read; (read = pipe.read(buffer)) != -1; ) {
        received.write(buffer, 0, read);
      }
    } catch (IOException error) {
      throw new IllegalStateException("waiting at the gate: " + error.getMessage(), error);
    }
    if (!Arrays.equals(received.toByteArray(), RELEASE)) {
      throw new IllegalStateException("the launcher closed the gate without releasing it");
    }
  }
}
