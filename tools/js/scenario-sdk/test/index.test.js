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

  it("flushes traces and logs before metrics, then shuts down", async () => {
    const events = [];
    let finishTrace;
    let finishLog;
    const traceDone = new Promise((resolve) => (finishTrace = resolve));
    const logDone = new Promise((resolve) => (finishLog = resolve));
    const runScenario = loadRunScenario(
      class {
        _tracerProvider = {
          forceFlush: () => {
            events.push("trace started");
            return traceDone.then(() => events.push("trace finished"));
          },
        };
        _loggerProvider = {
          forceFlush: () => {
            events.push("log started");
            return logDone.then(() => events.push("log finished"));
          },
        };
        _meterProvider = {
          forceFlush: () => events.push("metric"),
        };

        start() {}

        async shutdown() {
          events.push("shutdown");
        }
      },
    );

    const running = runScenario({}, () => events.push("scenario"));
    await new Promise(setImmediate);
    assert.deepEqual(events, ["scenario", "trace started", "log started"]);

    finishTrace();
    await new Promise(setImmediate);
    assert.equal(events.includes("metric"), false);
    finishLog();
    await running;

    assert.deepEqual(events, [
      "scenario",
      "trace started",
      "log started",
      "trace finished",
      "log finished",
      "metric",
      "shutdown",
    ]);
  });

  it("turns a flush failure into a failed run and still shuts down", async () => {
    const failure = new Error("flush failed");
    let finishLog;
    const logDone = new Promise((resolve) => (finishLog = resolve));
    let shutdown = false;
    const runScenario = loadRunScenario(
      class {
        _tracerProvider = { forceFlush: () => Promise.reject(failure) };
        _loggerProvider = { forceFlush: () => logDone };

        start() {}

        async shutdown() {
          shutdown = true;
        }
      },
    );

    const running = captureFailure(() => runScenario({}, () => {}));
    await new Promise(setImmediate);
    assert.equal(shutdown, false);

    finishLog();
    const result = await running;

    assert.equal(shutdown, true);
    assert.equal(result.exitCode, 1);
    assert.deepEqual(result.errors, [failure]);
  });

  it("turns a flush timeout into a failed run and still shuts down", async () => {
    const originalSetTimeout = global.setTimeout;
    global.setTimeout = (callback) => {
      queueMicrotask(callback);
      return {};
    };
    let shutdown = false;
    const runScenario = loadRunScenario(
      class {
        _tracerProvider = { forceFlush: () => new Promise(() => {}) };

        start() {}

        async shutdown() {
          shutdown = true;
        }
      },
    );

    try {
      const result = await captureFailure(() => runScenario({}, () => {}));

      assert.equal(shutdown, true);
      assert.equal(result.exitCode, 1);
      assert.match(result.errors[0].message, /flush timed out/);
    } finally {
      global.setTimeout = originalSetTimeout;
    }
  });
});
