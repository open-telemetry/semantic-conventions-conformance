/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario.sdk;

import io.opentelemetry.sdk.common.CompletableResultCode;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

final class TelemetryLifecycle {
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
    await("metric", flushMetrics.get(), remainingMillis(deadline));
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
