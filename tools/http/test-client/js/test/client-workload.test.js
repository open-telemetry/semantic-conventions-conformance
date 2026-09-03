// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  ACTIONS_VARIABLE,
  ACTION_VARIABLE,
  drive,
  requests,
  respond,
} = require("../src");
const { ACTIONS, ACTIONS_JSON } = require("./actions");

const BASE_URL = "http://127.0.0.1:0";
process.env[ACTIONS_VARIABLE] = ACTIONS_JSON;

async function withScenarioAction(index, callback) {
  const previous = process.env[ACTION_VARIABLE];
  process.env[ACTION_VARIABLE] = JSON.stringify(ACTIONS[index + 1]);
  try {
    return await callback();
  } finally {
    if (previous === undefined) {
      delete process.env[ACTION_VARIABLE];
    } else {
      process.env[ACTION_VARIABLE] = previous;
    }
  }
}

/** A sender backed by the other side of the same contract, which is what a run measures. */
async function driveAgainstTheContract() {
  const sent = [];
  for (let index = 0; index < requests().length; index += 1) {
    await withScenarioAction(index, () =>
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

  it("does not validate the response", async () => {
    const previous = process.env[ACTION_VARIABLE];
    await withScenarioAction(0, () =>
      drive(BASE_URL, () => ({ status: 599, body: "not json" })),
    );
    assert.equal(process.env[ACTION_VARIABLE], previous);
  });

  it("refuses a blank base URL before anything is sent", async () => {
    await withScenarioAction(0, () =>
      assert.rejects(
        () => drive("  ", () => ({ status: 200, body: "{}" })),
        TypeError,
      ),
    );
  });
});
