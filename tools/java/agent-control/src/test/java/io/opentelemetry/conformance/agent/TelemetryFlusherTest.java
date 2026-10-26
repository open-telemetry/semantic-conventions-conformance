/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.agent;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.opentelemetry.sdk.common.CompletableResultCode;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;

class TelemetryFlusherTest {
  @Test
  void startsAndAwaitsTracesAndLogsBeforeMetrics() throws Exception {
    TelemetryFlusher flusher = new TelemetryFlusher();
    List<String> events = new ArrayList<>();
    CompletableResultCode trace = new CompletableResultCode();
    CompletableResultCode log = new CompletableResultCode();
    CountDownLatch started = new CountDownLatch(2);
    flusher.addTrace(() -> pending("trace", events, started, trace));
    flusher.addLog(() -> pending("log", events, started, log));
    flusher.addMetric(
        () -> {
          events.add("metric");
          return CompletableResultCode.ofSuccess();
        });

    try (ExecutorService executor = Executors.newSingleThreadExecutor()) {
      Future<?> flushing = executor.submit(() -> flusher.flushTracesAndLogs(1_000));
      assertTrue(started.await(1, TimeUnit.SECONDS));
      assertEquals(List.of("trace", "log"), events);
      assertFalse(flushing.isDone());

      trace.succeed();
      assertFalse(flushing.isDone());
      log.succeed();
      flushing.get();
      flusher.flushMetrics(1_000);
    }

    assertEquals(List.of("trace", "log", "metric"), events);
  }

  @Test
  void failureIsPropagated() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    flusher.addLog(CompletableResultCode::ofFailure);

    assertThrows(IllegalStateException.class, () -> flusher.flushTracesAndLogs(1_000));
  }

  @Test
  void timeoutIsPropagated() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    flusher.addTrace(CompletableResultCode::new);

    assertThrows(IllegalStateException.class, () -> flusher.flushTracesAndLogs(0));
  }

  private static CompletableResultCode pending(
      String signal, List<String> events, CountDownLatch started, CompletableResultCode result) {
    events.add(signal);
    started.countDown();
    return result;
  }
}
