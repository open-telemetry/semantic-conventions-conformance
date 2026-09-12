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

const FLUSH_TIMEOUT_MILLIS = 15_000;

function remaining(deadline) {
  return Math.max(0, deadline - performance.now());
}

async function within(promise, timeoutMillis, phase) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`${phase} flush timed out`)),
      timeoutMillis,
    );
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

async function flushBeforeShutdown(sdk) {
  const deadline = performance.now() + FLUSH_TIMEOUT_MILLIS;
  // NodeSDK exposes only shutdown publicly. The pinned implementation retains
  // its providers here, so the adapter can order their flushes.
  const traceAndLogProviders = [
    sdk._tracerProvider,
    sdk._loggerProvider,
  ].filter(Boolean);
  const results = await within(
    Promise.allSettled(
      traceAndLogProviders.map((provider) => provider.forceFlush()),
    ),
    remaining(deadline),
    "trace and log",
  );
  const failure = results.find((result) => result.status === "rejected");
  if (failure) {
    throw failure.reason;
  }

  if (sdk._meterProvider) {
    await within(
      sdk._meterProvider.forceFlush(),
      remaining(deadline),
      "metric",
    );
  }
}

/**
 * Runs `workload` with the SDK started, then shuts it down.
 *
 * `workload` is a function rather than a promise so the library under test is
 * loaded after the instrumentations are registered: Node's instrumentations
 * patch a module as it is required, and one required earlier is never patched.
 *
 * Any SDK lifecycle or workload failure fails the run, because the runner
 * reads a scenario's result from its exit code.
 */
async function runScenario({ instrumentations = [] } = {}, workload) {
  try {
    // Failing here rather than exporting nowhere: a scenario that quietly
    // dropped its telemetry would be reported as producing none.
    requireEnv("OTEL_EXPORTER_OTLP_ENDPOINT");
    const sdk = new NodeSDK({ instrumentations });
    sdk.start();
    try {
      await workload();
    } finally {
      try {
        await flushBeforeShutdown(sdk);
      } finally {
        await sdk.shutdown();
      }
    }
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
}

module.exports = { runScenario };
