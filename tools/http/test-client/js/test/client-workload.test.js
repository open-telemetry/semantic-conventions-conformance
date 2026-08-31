// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { drive, requests, respond, SCENARIO_INDEX_VARIABLE } = require("../src");

const BASE_URL = "http://127.0.0.1:0";

/** A sender backed by the other side of the same contract, which is what a run measures. */
async function driveAgainstTheContract() {
  const sent = [];
  for (let index = 0; index < requests().length; index += 1) {
    process.env[SCENARIO_INDEX_VARIABLE] = String(index);
    await drive(BASE_URL, (method, url, body) => {
      const target = url.slice(BASE_URL.length);
      sent.push(`${method} ${target}`);
      return respond(method, target, body);
    });
  }
  delete process.env[SCENARIO_INDEX_VARIABLE];
  return sent;
}

describe("driving the contract", () => {
  it("has both sides agree", async () => {
    assert.deepEqual(await driveAgainstTheContract(), [
      "GET /users/123",
      "GET /users/123?fields=name&verbose=true",
      "POST /items",
      "GET /status/404",
      "GET /status/500",
    ]);
  });

  it("fails on a wrong response", async () => {
    process.env[SCENARIO_INDEX_VARIABLE] = "0";
    await assert.rejects(
      () => drive(BASE_URL, () => ({ status: 599, body: "not json" })),
      /answered 599/,
    );
    delete process.env[SCENARIO_INDEX_VARIABLE];
  });

  it("refuses a blank base URL before anything is sent", async () => {
    process.env[SCENARIO_INDEX_VARIABLE] = "0";
    await assert.rejects(
      () => drive("  ", () => ({ status: 200, body: "{}" })),
      TypeError,
    );
    delete process.env[SCENARIO_INDEX_VARIABLE];
  });
});
