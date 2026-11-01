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
import java.util.logging.Logger;

public final class TelemetryFlusher implements AgentControlMBean {
  private static final Logger logger = Logger.getLogger(TelemetryFlusher.class.getName());

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
    long deadline = System.nanoTime() + Math.max(0, timeoutMillis) * 1_000_000;
    for (Supplier<CompletableResultCode> operation : metrics) {
      boolean retryLogged = false;
      while (true) {
        CompletableResultCode result = operation.get();
        result.join(Math.max(0, (deadline - System.nanoTime()) / 1_000_000), TimeUnit.MILLISECONDS);
        if (result.isSuccess()) {
          break;
        }
        Throwable failure = result.getFailureThrowable();
        // Persistent scenarios export periodically, so a final flush can race
        // with the reader's previous export. It must still complete a new flush.
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
          TimeUnit.NANOSECONDS.sleep(
              Math.min(10_000_000, Math.max(0, deadline - System.nanoTime())));
        } catch (InterruptedException exception) {
          Thread.currentThread().interrupt();
          throw new IllegalStateException("metric flush was interrupted", exception);
        }
      }
    }
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
