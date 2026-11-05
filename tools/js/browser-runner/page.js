// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The page half of a browser scenario. Bundled into the page, and also read by
 * the launcher for the paths and the deadline helper both halves share.
 */

/** Everything the launcher serves itself sits under here; the rest is proxied. */
const BRIDGE_PATH = "/_otel-conformance";

/** Where the page exports `signal` ("traces", "metrics" or "logs"). */
function exportUrl(signal) {
  return new URL(`${BRIDGE_PATH}/v1/${signal}`, location.href).href;
}

/** Rejects with `describe()` if `promise` has not settled within `millis`. */
function within(promise, millis, describe) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(describe())), millis);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/**
 * Hands `workload` to the launcher, which calls it once with the scenario's
 * data and waits for what it returns.
 */
function exposeScenario(workload) {
  globalThis.runScenario = workload;
}

module.exports = { BRIDGE_PATH, exportUrl, exposeScenario, within };
