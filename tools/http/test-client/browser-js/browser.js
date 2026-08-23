// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-proto");
const { SimpleSpanProcessor } = require("@opentelemetry/sdk-trace-base");
const { WebTracerProvider } = require("@opentelemetry/sdk-trace-web");
const { verify } = require("./verify");

function config() {
  const value = window.__OTEL_HTTP_CONFORMANCE__;
  if (!value) {
    throw new Error("browser conformance configuration is missing");
  }
  return value;
}

function start(instrumentations) {
  let completedSpans = 0;
  const counter = {
    forceFlush: async () => {},
    onEnd: () => {
      completedSpans += 1;
    },
    onStart: () => {},
    shutdown: async () => {},
  };
  const provider = new WebTracerProvider({
    spanProcessors: [
      counter,
      new SimpleSpanProcessor(
        new OTLPTraceExporter({
          url: new URL(
            config().tracesEndpoint,
            window.location.origin,
          ).toString(),
        }),
      ),
    ],
  });
  provider.register();
  registerInstrumentations({ instrumentations, tracerProvider: provider });
  return { completedSpans: () => completedSpans, provider };
}

async function drive(send) {
  for (const exchange of config().requests) {
    const response = await send(
      exchange.method,
      `${window.location.origin}${exchange.path}`,
      exchange.body,
    );
    verify(exchange, response);
  }
}

function onLoad(callback) {
  if (document.readyState === "complete") {
    void callback();
  } else {
    window.addEventListener("load", () => void callback(), { once: true });
  }
}

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function finish(harness, error) {
  let failure = error;
  try {
    // Browser HTTP instrumentations wait briefly for PerformanceResourceTiming
    // entries before ending spans. Flush only after that observation window.
    await delay(1000);
    await harness.provider.forceFlush();
    if (harness.completedSpans() === 0) {
      failure ??= new Error("browser instrumentation completed no spans");
    }
    await harness.provider.shutdown();
  } catch (shutdownError) {
    failure ??= shutdownError;
  }
  await window.fetch(config().doneEndpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      ok: failure === undefined,
      error:
        failure instanceof Error
          ? (failure.stack ?? failure.message)
          : failure === undefined
            ? undefined
            : String(failure),
    }),
  });
}

module.exports = { drive, finish, onLoad, start };
