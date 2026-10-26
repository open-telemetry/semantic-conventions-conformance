/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.agent;

import io.opentelemetry.sdk.common.CompletableResultCode;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

public final class TelemetryFlusher implements AgentControlMBean {
  private final List<Supplier<CompletableResultCode>> traces = new CopyOnWriteArrayList<>();
  private final List<Supplier<CompletableResultCode>> logs = new CopyOnWriteArrayList<>();
  private final List<Supplier<CompletableResultCode>> metrics = new CopyOnWriteArrayList<>();

  void addTrace(Supplier<CompletableResultCode> operation) {
    traces.add(operation);
  }

  void addLog(Supplier<CompletableResultCode> operation) {
    logs.add(operation);
  }

  void addMetric(Supplier<CompletableResultCode> operation) {
    metrics.add(operation);
  }

  @Override
  public void flushTracesAndLogs(long timeoutMillis) {
    List<Supplier<CompletableResultCode>> operations = new ArrayList<>(traces);
    operations.addAll(logs);
    flush("trace and log", operations, timeoutMillis);
  }

  @Override
  public void flushMetrics(long timeoutMillis) {
    flush("metric", metrics, timeoutMillis);
  }

  private static void flush(
      String phase, List<Supplier<CompletableResultCode>> operations, long timeoutMillis) {
    List<CompletableResultCode> results = new ArrayList<>();
    for (Supplier<CompletableResultCode> operation : operations) {
      try {
        results.add(operation.get());
      } catch (RuntimeException exception) {
        results.add(CompletableResultCode.ofExceptionalFailure(exception));
      }
    }

    CompletableResultCode result = CompletableResultCode.ofAll(results);
    result.join(Math.max(0, timeoutMillis), TimeUnit.MILLISECONDS);
    if (!result.isSuccess()) {
      throw new IllegalStateException(
          phase + " flush did not complete within the shutdown budget",
          result.getFailureThrowable());
    }
  }
}
