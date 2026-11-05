// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { within } = require("../page");

/** Exercise the real provider and processor with a controlled OTLP exporter. */
function run(results) {
  let provider;
  let exported = 0;
  class Exporter {
    export(_spans, callback) {
      callback(results[exported++]);
    }
    async forceFlush() {
      while (exported < results.length) {
        provider.getTracer("test").startSpan("late export").end();
      }
    }
    async shutdown() {}
  }

  const dependencies = {
    "@opentelemetry/exporter-trace-otlp-proto": {
      OTLPTraceExporter: Exporter,
    },
    "@opentelemetry/instrumentation": {
      registerInstrumentations({ tracerProvider }) {
        provider = tracerProvider;
      },
    },
    "./page": { exportUrl: () => "http://localhost/v1/traces", within },
  };
  const module = { exports: {} };
  const filename = path.resolve(__dirname, "../tracing.js");
  vm.compileFunction(fs.readFileSync(filename, "utf8"), ["require", "module"], {
    filename,
  })((name) => dependencies[name] ?? require(name), module);

  return module.exports
    .runWithTracing({
      instrumentations: [],
      expectedSpans: 1,
      workload() {
        provider.getTracer("test").startSpan("expected export").end();
        return "answered";
      },
    })
    .finally(() => provider.shutdown());
}

test("accepts exactly the expected number of successful exports", async () => {
  assert.equal(await run([{ code: 0 }]), "answered");
});

test("rejects extra exports after the expected count was reached", async () => {
  await assert.rejects(
    run([{ code: 0 }, { code: 0 }, { code: 0 }]),
    /exported 3 spans, expected 1/,
  );
});

test("rejects export failures after the expected count was reached", async () => {
  const failure = new Error("late OTLP failure");
  await assert.rejects(
    run([{ code: 0 }, { code: 1, error: failure }]),
    failure,
  );
});

test("rejects a failure before the expected count was reached", async () => {
  const failure = new Error("first OTLP failure");
  await assert.rejects(run([{ code: 1, error: failure }]), failure);
});
