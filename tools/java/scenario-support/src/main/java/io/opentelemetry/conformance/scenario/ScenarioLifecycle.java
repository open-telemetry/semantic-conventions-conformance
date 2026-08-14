/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import java.io.IOException;

/** How a long-running scenario learns that the runner is finished with it. */
public final class ScenarioLifecycle {
  private ScenarioLifecycle() {}

  /**
   * Blocks until standard input closes, which is how the driver says stop.
   *
   * <p>A closed pipe rather than a signal: it means the same thing on every platform, and returning
   * is what gives an SDK the chance to flush, so a scenario that exits any other way reports less
   * than it produced. The protocol is the same in every domain.
   */
  public static void waitForEof() throws IOException {
    while (System.in.read() != -1) {
      // Nothing arrives on standard input; only its close is the signal.
    }
  }
}
