// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { PORT_VARIABLE, respond, scenarioPort } = require("../src");

describe("answering the contract", () => {
  it("takes an answer from the contract", () => {
    const answer = respond("GET", "/status/500");

    assert.equal(answer.status, 500);
    assert.equal(answer.body, '{"message": "status 500"}');
  });

  it("finds the route through the concrete path the framework reports", () => {
    const answer = respond("GET", "/users/123?fields=name");

    assert.equal(answer.status, 200);
  });

  it("echoes the body, so a scenario that never read it fails", () => {
    const answer = respond("POST", "/items", '{"name": "widget"}');

    assert.equal(answer.status, 201);
    assert.equal(
      answer.body,
      '{"created": true, "payload": {"name": "widget"}}',
    );
  });

  it("refuses traffic the contract does not describe", () => {
    assert.equal(respond("GET", "/nope").status, 404);
  });
});

describe("the port the driver chose", () => {
  it("says who sets it when it is missing", () => {
    const previous = process.env[PORT_VARIABLE];
    delete process.env[PORT_VARIABLE];
    try {
      assert.throws(() => scenarioPort(), /otel-http-drive/);
    } finally {
      if (previous !== undefined) {
        process.env[PORT_VARIABLE] = previous;
      }
    }
  });

  it("names a value that is not a port", () => {
    const previous = process.env[PORT_VARIABLE];
    process.env[PORT_VARIABLE] = "not-a-port";
    try {
      assert.throws(() => scenarioPort(), /not-a-port/);
    } finally {
      if (previous === undefined) {
        delete process.env[PORT_VARIABLE];
      } else {
        process.env[PORT_VARIABLE] = previous;
      }
    }
  });
});
