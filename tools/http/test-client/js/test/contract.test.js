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
});
