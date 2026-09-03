// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { drive, requests, respond, SCENARIO_INDEX_VARIABLE } = require("../src");

const BASE_URL = "http://127.0.0.1:0";

async function withScenarioIndex(index, callback) {
  const previous = process.env[SCENARIO_INDEX_VARIABLE];
  process.env[SCENARIO_INDEX_VARIABLE] = String(index);
  try {
    return await callback();
  } finally {
    if (previous === undefined) {
      delete process.env[SCENARIO_INDEX_VARIABLE];
    } else {
      process.env[SCENARIO_INDEX_VARIABLE] = previous;
    }
  }
}

/** A sender backed by the other side of the same contract, which is what a run measures. */
async function driveAgainstTheContract() {
  const sent = [];
  for (let index = 0; index < requests().length; index += 1) {
    await withScenarioIndex(index, () =>
      drive(BASE_URL, (method, url, body) => {
        const target = url.slice(BASE_URL.length);
        sent.push(`${method} ${target}`);
        return respond(method, target, body);
      }),
    );
  }
  return sent;
}

describe("driving the contract", () => {
  it("sends every contract request", async () => {
    assert.deepEqual(await driveAgainstTheContract(), [
      "GET /users/123",
      "GET /users/123?fields=name&verbose=true",
      "POST /items",
      "GET /status/404",
      "GET /status/500",
    ]);
  });

  it("rejects a response outside the contract", async () => {
    await withScenarioIndex(0, () =>
      assert.rejects(
        () => drive(BASE_URL, () => ({ status: 599, body: "not json" })),
        /answered 599/,
      ),
    );
  });

  it("accepts equivalent JSON with a different object key order", async () => {
    await withScenarioIndex(0, () =>
      drive(BASE_URL, () => ({
        status: 200,
        body: '{"name":"Alice","id":123}',
      })),
    );
  });

  it("refuses a blank base URL before anything is sent", async () => {
    await withScenarioIndex(0, () =>
      assert.rejects(
        () => drive("  ", () => ({ status: 200, body: "{}" })),
        TypeError,
      ),
    );
  });
});
