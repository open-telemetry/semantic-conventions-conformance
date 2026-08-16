// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The OpenTelemetry SDK a scenario configures for itself.
 *
 * Only a scenario measuring instrumentation it registers itself needs this. A
 * scenario measuring an auto-instrumentation runtime has its SDK configured
 * for it, and must not carry these packages at all.
 *
 * Everything but the instrumentations comes from the environment the runner
 * injected — the OTLP endpoint, its protocol, and the export interval — so a
 * scenario names only what it is measuring.
 */

const { NodeSDK } = require("@opentelemetry/sdk-node");
const { requireEnv } = require("@otel-conformance/scenario-support");

/**
 * Runs `workload` with the SDK started, then shuts it down.
 *
 * `workload` is a function rather than a promise so the library under test is
 * loaded after the instrumentations are registered: Node's instrumentations
 * patch a module as it is required, and one required earlier is never patched.
 *
 * Shutting the SDK down is what flushes, so it happens whether the workload
 * finished or threw — and a workload that threw fails the run, because the
 * runner reads a scenario's result from its exit code.
 */
async function runScenario({ instrumentations = [] } = {}, workload) {
  // Failing here rather than exporting nowhere: a scenario that quietly
  // dropped its telemetry would be reported as producing none.
  requireEnv("OTEL_EXPORTER_OTLP_ENDPOINT");
  const sdk = new NodeSDK({ instrumentations });
  sdk.start();
  try {
    await workload();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    await sdk.shutdown();
  }
}

module.exports = { runScenario };
