/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario.sdk;

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

class TelemetryLifecycleTest {
  @Test
  void startsAndAwaitsTracesAndLogsBeforeMetrics() throws Exception {
    List<String> events = new ArrayList<>();
    CountDownLatch started = new CountDownLatch(2);
    CompletableResultCode trace = new CompletableResultCode();
    CompletableResultCode log = new CompletableResultCode();

    try (ExecutorService executor = Executors.newSingleThreadExecutor()) {
      Future<?> flushing =
          executor.submit(
              () ->
                  TelemetryLifecycle.flushBeforeShutdown(
                      () -> pending("trace", events, started, trace),
                      () -> pending("log", events, started, log),
                      () -> completed("metric", events),
                      1_000));

      assertTrue(started.await(1, TimeUnit.SECONDS));
      assertEquals(List.of("trace", "log"), events);
      assertFalse(flushing.isDone());
      trace.succeed();
      assertFalse(flushing.isDone());
      log.succeed();
      flushing.get();
    }

    assertEquals(List.of("trace", "log", "metric"), events);
  }

  @Test
  void failureIsPropagatedBeforeMetrics() {
    List<String> events = new ArrayList<>();

    assertThrows(
        IllegalStateException.class,
        () ->
            TelemetryLifecycle.flushBeforeShutdown(
                CompletableResultCode::ofSuccess,
                CompletableResultCode::ofFailure,
                () -> completed("metric", events),
                1_000));

    assertEquals(List.of(), events);
  }

  @Test
  void timeoutIsPropagated() {
    assertThrows(
        IllegalStateException.class,
        () ->
            TelemetryLifecycle.flushBeforeShutdown(
                CompletableResultCode::new,
                CompletableResultCode::ofSuccess,
                CompletableResultCode::ofSuccess,
                0));
  }

  private static CompletableResultCode pending(
      String signal, List<String> events, CountDownLatch started, CompletableResultCode result) {
    events.add(signal);
    started.countDown();
    return result;
  }

  private static CompletableResultCode completed(String signal, List<String> events) {
    events.add(signal);
    return CompletableResultCode.ofSuccess();
  }
}
