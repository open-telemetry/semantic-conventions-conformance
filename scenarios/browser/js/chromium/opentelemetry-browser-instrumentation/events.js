// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * What every page here shares: the logs SDK, exporting through the shared
 * browser runner, and a wait for the events the page expects.
 *
 * Bundled into the page, never loaded by Node.
 */

const {
  BatchLogRecordProcessor,
  LoggerProvider,
} = require("@opentelemetry/sdk-logs");
const { OTLPLogExporter } = require("@opentelemetry/exporter-logs-otlp-proto");
const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const {
  exportUrl,
  exposeScenario,
  within,
} = require("@otel-conformance/browser-runner/page");

const EVENTS_TIMEOUT_MILLIS = 20_000;

/**
 * Counts records by event name. `emitted()` resolves once each event in
 * `expected` has been seen at least as often as it says, since a browser
 * event arrives from a listener or an observer after the workload returned.
 */
function counting(expected) {
  const seen = {};
  let wake = () => {};
  const done = () =>
    Object.entries(expected).every(([name, count]) => seen[name] >= count);
  return {
    seen,
    emitted: () =>
      done() ? Promise.resolve() : new Promise((resolve) => (wake = resolve)),
    processor: {
      onEmit(record) {
        const name = record.eventName ?? "";
        seen[name] = (seen[name] ?? 0) + 1;
        if (done()) {
          wake();
        }
      },
      forceFlush: async () => {},
      shutdown: async () => {},
    },
  };
}

/**
 * Registers `instrumentations` and hands `workload` to the runner, which
 * calls it once and waits until the `events` it names have been emitted and
 * their export answered.
 */
function exposeEvents({ instrumentations = [], events = {} } = {}, workload) {
  const counted = counting(events);
  const provider = new LoggerProvider({
    processors: [
      new BatchLogRecordProcessor({
        exporter: new OTLPLogExporter({ url: exportUrl("logs") }),
      }),
      counted.processor,
    ],
  });
  registerInstrumentations({ instrumentations, loggerProvider: provider });

  exposeScenario(async () => {
    await workload();
    await within(
      counted.emitted(),
      EVENTS_TIMEOUT_MILLIS,
      () =>
        `expected events ${JSON.stringify(events)}, ` +
        `emitted ${JSON.stringify(counted.seen)}`,
    );
    // Resolves when the relay has answered, which it does only after the
    // runner's bridge has handed the records to weaver.
    await provider.forceFlush();
    return counted.seen;
  });
}

module.exports = { exposeEvents };
