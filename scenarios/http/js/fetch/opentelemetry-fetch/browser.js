// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-proto");
const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const {
  FetchInstrumentation,
} = require("@opentelemetry/instrumentation-fetch");
const {
  SimpleSpanProcessor,
  TracerProvider,
} = require("@opentelemetry/sdk-trace");
const {
  BRIDGE_PATH,
  exportUrl,
  exposeScenario,
  within,
} = require("@otel-conformance/browser-runner/page");
const { drive } = require("@otel-conformance/fetch-scenarios");

const SPANS_TIMEOUT_MILLIS = 20_000;

/**
 * Counts the spans the exporter has handed on. Fetch instrumentation ends a
 * span only after the response and its resource timing arrive, so the spans
 * come after the workload returned.
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
        () => `expected ${expected} Fetch spans, exported ${exported}`,
      );
    },
  };
}

exposeScenario(async ({ exchanges }) => {
  const exporter = trackingExporter(
    new OTLPTraceExporter({ url: exportUrl("traces") }),
    exchanges.filter((exchange) => !exchange.readiness).length,
  );
  const provider = new TracerProvider({
    spanProcessors: [new SimpleSpanProcessor({ exporter })],
  });
  registerInstrumentations({
    tracerProvider: provider,
    instrumentations: [
      new FetchInstrumentation({ ignoreUrls: [new RegExp(`${BRIDGE_PATH}/`)] }),
    ],
  });
  const answered = await drive(location.origin, exchanges);
  await exporter.waitForExpectedSpans();
  await provider.forceFlush();
  return answered;
});
