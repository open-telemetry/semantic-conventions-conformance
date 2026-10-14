/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario.sdk;

import io.opentelemetry.sdk.common.CompletableResultCode;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;
import java.util.logging.Logger;

final class TelemetryLifecycle {
  private static final Logger logger = Logger.getLogger(TelemetryLifecycle.class.getName());

  private TelemetryLifecycle() {}

  static void flushBeforeShutdown(
      Supplier<CompletableResultCode> flushTraces,
      Supplier<CompletableResultCode> flushLogs,
      Supplier<CompletableResultCode> flushMetrics,
      long timeoutMillis) {
    long deadline = System.nanoTime() + timeoutMillis * 1_000_000;
    CompletableResultCode tracesAndLogs =
        CompletableResultCode.ofAll(List.of(flushTraces.get(), flushLogs.get()));
    await("trace and log", tracesAndLogs, remainingMillis(deadline));
    boolean retryLogged = false;
    while (true) {
      CompletableResultCode result = flushMetrics.get();
      result.join(remainingMillis(deadline), TimeUnit.MILLISECONDS);
      if (result.isSuccess()) {
        return;
      }
      Throwable failure = result.getFailureThrowable();
      // The periodic reader can skip a flush while an export is in flight.
      // Retry within the original budget, never accepting the skipped flush.
      if (!(failure instanceof IllegalStateException)
          || !"Export is already in progress, skipping flush".equals(failure.getMessage())
          || System.nanoTime() >= deadline) {
        throw new IllegalStateException(
            "metric flush did not complete within the shutdown budget", failure);
      }
      if (!retryLogged) {
        logger.warning("Retrying metric flush after the periodic reader skipped it");
        retryLogged = true;
      }
      try {
        TimeUnit.NANOSECONDS.sleep(Math.min(10_000_000, Math.max(0, deadline - System.nanoTime())));
      } catch (InterruptedException exception) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException("metric flush was interrupted", exception);
      }
    }
  }

  private static void await(String phase, CompletableResultCode result, long timeoutMillis) {
    result.join(timeoutMillis, TimeUnit.MILLISECONDS);
    if (!result.isSuccess()) {
      throw new IllegalStateException(
          phase + " flush did not complete within the shutdown budget",
          result.getFailureThrowable());
    }
  }

  private static long remainingMillis(long deadline) {
    return Math.max(0, (deadline - System.nanoTime()) / 1_000_000);
  }
}
