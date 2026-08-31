// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  exchangeFor,
  exchanges,
  renderResponseBody,
  requests,
  scenarioRequest,
} = require("../src");

describe("the contract", () => {
  it("is read from the file every language reads", () => {
    assert.ok(exchanges().length > 0);
  });

  it("does not measure readiness", () => {
    assert.ok(exchanges().some((exchange) => exchange.readiness));
    assert.ok(!requests().some((exchange) => exchange.readiness));
    assert.equal(requests().length, exchanges().length - 1);
  });

  it("selects each request by its independent ordinal", () => {
    requests().forEach((exchange, index) => {
      assert.equal(scenarioRequest(index), exchange);
    });
    assert.throws(() => scenarioRequest(-1), /zero-based decimal/);
    assert.throws(() => scenarioRequest(requests().length), /selects no/);
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
