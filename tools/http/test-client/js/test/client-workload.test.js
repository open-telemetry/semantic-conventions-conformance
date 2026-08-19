// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  ContractError,
  drive,
  exchangeFor,
  respond,
  verify,
} = require("../src");

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

  it("fails the run on a wrong status", () => {
    const users = exchangeFor("GET", "/users/123");

    assert.throws(
      () => verify(users, { status: 500, body: users.responseBody }),
      (error) =>
        error instanceof ContractError &&
        error.message.includes("answered 500"),
    );
  });

  it("leaves whitespace and key order to the JSON writer", () => {
    const users = exchangeFor("GET", "/users/123");

    verify(users, {
      status: users.status,
      body: '{ "name" :"Alice",\n  "id": 123 }',
    });
  });

  it("says so when an answer is not JSON", () => {
    const users = exchangeFor("GET", "/users/123");

    assert.throws(
      () => verify(users, { status: users.status, body: "<html>" }),
      (error) =>
        error instanceof ContractError && error.message.startsWith("not JSON"),
    );
  });

  it("refuses a blank base URL before anything is sent", async () => {
    await assert.rejects(
      () => drive("  ", () => ({ status: 200, body: "{}" })),
      TypeError,
    );
  });
});
