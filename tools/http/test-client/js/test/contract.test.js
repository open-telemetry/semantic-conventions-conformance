// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  ACTIONS_VARIABLE,
  ACTION_VARIABLE,
  exchangeFor,
  exchanges,
  renderResponseBody,
  requests,
  scenarioRequest,
} = require("../src");
const { ACTIONS, ACTIONS_JSON } = require("./actions");

process.env[ACTIONS_VARIABLE] = ACTIONS_JSON;

describe("the contract", () => {
  it("decodes the complete runner action table", () => {
    assert.ok(exchanges().length > 0);
  });

  it("does not measure readiness", () => {
    assert.ok(exchanges().some((exchange) => exchange.readiness));
    assert.ok(!requests().some((exchange) => exchange.readiness));
    assert.equal(requests().length, exchanges().length - 1);
  });

  it("selects each singular client action", () => {
    requests().forEach((exchange, index) => {
      assert.deepEqual(
        scenarioRequest(JSON.stringify(ACTIONS[index + 1])),
        exchange,
      );
    });
  });

  it("says when the selected action is not set", () => {
    const previous = process.env[ACTION_VARIABLE];
    delete process.env[ACTION_VARIABLE];
    try {
      assert.throws(
        () => scenarioRequest(),
        new RegExp(`${ACTION_VARIABLE} is not set`),
      );
    } finally {
      if (previous === undefined) {
        delete process.env[ACTION_VARIABLE];
      } else {
        process.env[ACTION_VARIABLE] = previous;
      }
    }
  });

  it("rejects malformed JSON and unknown action fields", () => {
    assert.throws(() => scenarioRequest("{"), /malformed JSON/);
    assert.throws(() => exchanges("{"), /malformed JSON/);
    assert.throws(
      () => scenarioRequest('{"request":{},"response":{},"extra":true}'),
      /unknown field/,
    );
  });

  it("says when the complete action table is not set", () => {
    const previous = process.env[ACTIONS_VARIABLE];
    delete process.env[ACTIONS_VARIABLE];
    try {
      assert.throws(
        () => exchanges(),
        new RegExp(`${ACTIONS_VARIABLE} is not set`),
      );
    } finally {
      process.env[ACTIONS_VARIABLE] = previous;
    }
  });

  // A field this reader names but the contract does not is `undefined` here
  // rather than an error, so only a check on the value catches a rename.
  it("carries every field the contract names", () => {
    for (const exchange of exchanges()) {
      assert.equal(typeof exchange.description, "string");
      assert.ok(exchange.description.trim().length > 0);
      assert.equal(typeof exchange.method, "string");
      assert.equal(typeof exchange.path, "string");
      assert.equal(typeof exchange.status, "number");
      assert.equal(typeof exchange.responseBody, "string");
    }
  });

  it("answers the same exchange with or without a query string", () => {
    const plain = exchangeFor("GET", "/users/123");
    const withQuery = exchangeFor("GET", "/users/123?fields=name&verbose=true");

    assert.equal(plain.status, withQuery.status);
    assert.equal(plain.responseBody, withQuery.responseBody);
  });

  it("looks up the method as well as the path", () => {
    assert.equal(exchangeFor("DELETE", "/items"), null);
  });

  it("describes no exchange for an unknown path", () => {
    assert.equal(exchangeFor("GET", "/nope"), null);
  });

  it("echoes the body that arrived", () => {
    const items = exchangeFor("POST", "/items");

    assert.equal(
      renderResponseBody(items, '{"name": "widget"}'),
      '{"created": true, "payload": {"name": "widget"}}',
    );
  });

  it("echoes an empty object for a request that carried no body", () => {
    const items = exchangeFor("POST", "/items");

    assert.equal(
      renderResponseBody(items, null),
      renderResponseBody(items, ""),
    );
    assert.equal(
      renderResponseBody(items, null),
      '{"created": true, "payload": {}}',
    );
  });

  // `$&` and its siblings are substitution patterns to a JavaScript string
  // replacement, and to nothing at all in the readers the other languages use.
  it("echoes a body the way every other language reads it", () => {
    const items = exchangeFor("POST", "/items");

    assert.equal(
      renderResponseBody(items, '{"name": "a$&b$`c$\'d$$e"}'),
      '{"created": true, "payload": {"name": "a$&b$`c$\'d$$e"}}',
    );
  });
});
