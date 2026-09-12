/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

/** How a long-running scenario learns that the runner is finished with it. */
public final class ScenarioLifecycle {
  private static final AtomicBoolean EXIT_AFTER_FLUSH = new AtomicBoolean();

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

  /** Requests a forced process exit after the scenario's telemetry has been flushed. */
  public static void exitAfterFlush() {
    EXIT_AFTER_FLUSH.set(true);
  }

  static boolean takeExitAfterFlushRequest() {
    return EXIT_AFTER_FLUSH.getAndSet(false);
  }
}
