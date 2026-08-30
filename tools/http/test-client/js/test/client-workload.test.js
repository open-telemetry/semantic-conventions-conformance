// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { drive, respond } = require("../src");

const BASE_URL = "http://127.0.0.1:0";

/** A sender backed by the other side of the same contract, which is what a run measures. */
async function driveAgainstTheContract() {
  const sent = [];
  await drive(BASE_URL, (method, url, body) => {
    const target = url.slice(BASE_URL.length);
    sent.push(`${method} ${target}`);
    return respond(method, target, body);
  });
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

  it("leaves responses to the telemetry contract", async () => {
    let sent = 0;
    await drive(BASE_URL, () => {
      sent += 1;
      return {
        status: 599,
        body: "not json",
      };
    });
    assert.equal(sent, 5);
  });

  it("refuses a blank base URL before anything is sent", async () => {
    await assert.rejects(
      () => drive("  ", () => ({ status: 200, body: "{}" })),
      TypeError,
    );
  });
});
