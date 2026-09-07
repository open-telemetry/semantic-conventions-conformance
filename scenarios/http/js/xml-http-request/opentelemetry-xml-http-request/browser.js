// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-proto");
const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const {
  XMLHttpRequestInstrumentation,
} = require("@opentelemetry/instrumentation-xml-http-request");
const {
  SimpleSpanProcessor,
  WebTracerProvider,
} = require("@opentelemetry/sdk-trace-web");
const { drive } = require("@otel-conformance/xml-http-request-scenarios");

/** Resolves once exactly `expected` XMLHttpRequest spans have reached the exporter. */
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
      return complete;
    },
  };
}

async function run() {
  const { baseUrl, exchanges, traceExporterUrl } = window.__otelConformance;
  const exporter = trackingExporter(
    new OTLPTraceExporter({ url: traceExporterUrl }),
    exchanges.filter((exchange) => !exchange.readiness).length,
  );
  const provider = new WebTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  provider.register();
  registerInstrumentations({
    tracerProvider: provider,
    instrumentations: [
      new XMLHttpRequestInstrumentation({ ignoreUrls: [traceExporterUrl] }),
    ],
  });
  await drive(baseUrl, exchanges);
  await exporter.waitForExpectedSpans();
  await provider.forceFlush();
}

run().then(
  () => {
    window.__otelConformanceResult = { ok: true };
  },
  (error) => {
    window.__otelConformanceResult = {
      ok: false,
      error: String(error.stack || error),
    };
  },
);
