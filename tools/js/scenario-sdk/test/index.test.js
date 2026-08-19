// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const Module = require("node:module");
const { describe, it } = require("node:test");

const scenarioSdkPath = require.resolve("../index");

function loadRunScenario(NodeSDK) {
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "@opentelemetry/sdk-node") {
      return { NodeSDK };
    }
    if (request === "@otel-conformance/scenario-support") {
      return { requireEnv: () => {} };
    }
    return originalLoad.call(this, request, parent, isMain);
  };
  delete require.cache[scenarioSdkPath];
  try {
    return require(scenarioSdkPath).runScenario;
  } finally {
    Module._load = originalLoad;
    delete require.cache[scenarioSdkPath];
  }
}

async function captureFailure(operation) {
  const originalError = console.error;
  const errors = [];
  console.error = (error) => errors.push(error);
  process.exitCode = 0;
  try {
    await operation();
    return { errors, exitCode: process.exitCode };
  } finally {
    console.error = originalError;
    process.exitCode = 0;
  }
}

describe("running a scenario", () => {
  it("turns an SDK startup failure into a failed run", async () => {
    const failure = new Error("startup failed");
    const runScenario = loadRunScenario(
      class {
        start() {
          throw failure;
        }
      },
    );
    let workloadRan = false;

    const result = await captureFailure(() =>
      runScenario({}, () => {
        workloadRan = true;
      }),
    );

    assert.equal(workloadRan, false);
    assert.equal(result.exitCode, 1);
    assert.deepEqual(result.errors, [failure]);
  });

  it("turns an SDK shutdown failure into a failed run", async () => {
    const failure = new Error("shutdown failed");
    const runScenario = loadRunScenario(
      class {
        start() {}

        async shutdown() {
          throw failure;
        }
      },
    );
    let workloadRan = false;

    const result = await captureFailure(() =>
      runScenario({}, () => {
        workloadRan = true;
      }),
    );

    assert.equal(workloadRan, true);
    assert.equal(result.exitCode, 1);
    assert.deepEqual(result.errors, [failure]);
  });
});
