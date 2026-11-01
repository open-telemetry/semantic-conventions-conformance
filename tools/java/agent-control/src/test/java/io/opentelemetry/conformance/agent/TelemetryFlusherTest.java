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
import io.opentelemetry.sdk.metrics.InstrumentType;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.metrics.data.AggregationTemporality;
import io.opentelemetry.sdk.metrics.data.MetricData;
import io.opentelemetry.sdk.metrics.export.MetricExporter;
import io.opentelemetry.sdk.metrics.export.PeriodicMetricReader;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
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

  @Test
  void retriesSkippedMetricFlushWithoutRepeatingSuccessfulReaders() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    AtomicInteger successfulAttempts = new AtomicInteger();
    AtomicInteger skippedAttempts = new AtomicInteger();
    flusher.addMetric(
        () -> {
          successfulAttempts.incrementAndGet();
          return CompletableResultCode.ofSuccess();
        });
    flusher.addMetric(
        () ->
            skippedAttempts.incrementAndGet() == 1
                ? skippedMetricFlush()
                : CompletableResultCode.ofSuccess());

    flusher.flushMetrics(1_000);

    assertEquals(1, successfulAttempts.get());
    assertEquals(2, skippedAttempts.get());
  }

  @Test
  void skippedMetricFlushStillFailsWhenTheBudgetExpires() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    flusher.addMetric(TelemetryFlusherTest::skippedMetricFlush);

    assertThrows(IllegalStateException.class, () -> flusher.flushMetrics(20));
  }

  @Test
  void otherMetricFlushFailureIsNotRetried() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    AtomicInteger attempts = new AtomicInteger();
    flusher.addMetric(
        () -> {
          attempts.incrementAndGet();
          return CompletableResultCode.ofExceptionalFailure(
              new IllegalStateException("export failed"));
        });

    assertThrows(IllegalStateException.class, () -> flusher.flushMetrics(1_000));
    assertEquals(1, attempts.get());
  }

  @Test
  void pendingMetricFlushFailsWhenTheBudgetExpires() {
    TelemetryFlusher flusher = new TelemetryFlusher();
    flusher.addMetric(CompletableResultCode::new);

    assertThrows(IllegalStateException.class, () -> flusher.flushMetrics(0));
  }

  @Test
  void periodicReaderFlushWaitsForTheInFlightExport() throws Exception {
    CompletableResultCode firstExport = new CompletableResultCode();
    AtomicInteger exports = new AtomicInteger();
    PeriodicMetricReader reader =
        PeriodicMetricReader.builder(
                exporter(
                    () ->
                        exports.incrementAndGet() == 1
                            ? firstExport
                            : CompletableResultCode.ofSuccess(),
                    CompletableResultCode::ofSuccess))
            .setInterval(Duration.ofDays(1))
            .build();
    try (SdkMeterProvider provider =
            SdkMeterProvider.builder().registerMetricReader(reader).build();
        ExecutorService executor = Executors.newSingleThreadExecutor()) {
      provider.get("test").counterBuilder("requests").build().add(1);
      CompletableResultCode initialFlush = reader.forceFlush();
      CountDownLatch skipped = new CountDownLatch(1);
      TelemetryFlusher flusher = new TelemetryFlusher();
      flusher.addMetric(
          () -> {
            CompletableResultCode result = reader.forceFlush();
            if (result.isDone() && !result.isSuccess()) {
              skipped.countDown();
            }
            return result;
          });
      Future<?> flushing = executor.submit(() -> flusher.flushMetrics(1_000));
      try {
        assertTrue(skipped.await(1, TimeUnit.SECONDS));
      } finally {
        firstExport.succeed();
      }
      flushing.get(1, TimeUnit.SECONDS);

      assertTrue(initialFlush.isSuccess());
      assertTrue(exports.get() >= 2);
    }
  }

  @Test
  void permanentlyFailedMetricFlushCannotPass() {
    PeriodicMetricReader reader =
        PeriodicMetricReader.builder(
                exporter(CompletableResultCode::ofSuccess, CompletableResultCode::ofFailure))
            .setInterval(Duration.ofDays(1))
            .build();
    try (SdkMeterProvider provider =
        SdkMeterProvider.builder().registerMetricReader(reader).build()) {
      provider.get("test").counterBuilder("requests").build().add(1);
      TelemetryFlusher flusher = new TelemetryFlusher();
      flusher.addMetric(reader::forceFlush);

      assertThrows(IllegalStateException.class, () -> flusher.flushMetrics(20));
    }
  }

  private static MetricExporter exporter(
      Supplier<CompletableResultCode> exportResult, Supplier<CompletableResultCode> flushResult) {
    return new MetricExporter() {
      @Override
      public AggregationTemporality getAggregationTemporality(InstrumentType instrumentType) {
        return AggregationTemporality.CUMULATIVE;
      }

      @Override
      public CompletableResultCode export(Collection<MetricData> metrics) {
        return exportResult.get();
      }

      @Override
      public CompletableResultCode flush() {
        return flushResult.get();
      }

      @Override
      public CompletableResultCode shutdown() {
        return CompletableResultCode.ofSuccess();
      }
    };
  }

  private static CompletableResultCode skippedMetricFlush() {
    return CompletableResultCode.ofExceptionalFailure(
        new IllegalStateException("Export is already in progress, skipping flush"));
  }

  private static CompletableResultCode pending(
      String signal, List<String> events, CountDownLatch started, CompletableResultCode result) {
    events.add(signal);
    started.countDown();
    return result;
  }
}
