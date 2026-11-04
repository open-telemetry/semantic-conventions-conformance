// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-proto");
const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const {
  SimpleSpanProcessor,
  TracerProvider,
} = require("@opentelemetry/sdk-trace");
const { exportUrl, within } = require("./page");

const SPANS_TIMEOUT_MILLIS = 20_000;

/**
 * Counts the spans the exporter has handed on. Browser instrumentations can
 * finish spans after the workload returns, once resource timing arrives.
 */
function trackingExporter(exporter, expected) {
  let exported = 0;
  let resolve;
  let reject;
  const complete = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return {
    export(spans, callback) {
      exporter.export(spans, (result) => {
        callback(result);
        if (result.code !== 0) {
          reject(result.error || new Error("OTLP export failed"));
          return;
        }
        exported += spans.length;
        if (exported === expected) {
          resolve();
        } else if (exported > expected) {
          reject(new Error(`exported ${exported} spans, expected ${expected}`));
        }
      });
    },
    forceFlush() {
      return exporter.forceFlush();
    },
    shutdown() {
      return exporter.shutdown();
    },
    waitForExpectedSpans() {
      return within(
        complete,
        SPANS_TIMEOUT_MILLIS,
        () => `expected ${expected} spans, exported ${exported}`,
      );
    },
  };
}

/** Runs a browser workload after registering its tracing instrumentation. */
async function runWithTracing({ instrumentations, expectedSpans, workload }) {
  const exporter = trackingExporter(
    new OTLPTraceExporter({ url: exportUrl("traces") }),
    expectedSpans,
  );
  const provider = new TracerProvider({
    spanProcessors: [new SimpleSpanProcessor({ exporter })],
  });
  registerInstrumentations({ tracerProvider: provider, instrumentations });
  const answered = await workload();
  await exporter.waitForExpectedSpans();
  await provider.forceFlush();
  return answered;
}

module.exports = { runWithTracing };
