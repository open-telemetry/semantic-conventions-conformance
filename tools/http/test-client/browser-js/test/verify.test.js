// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { expectedBody, verify } = require("../verify");

const ITEMS = {
  method: "POST",
  path: "/items",
  body: '{"name": "widget"}',
  status: 201,
  responseBody: '{"created": true, "payload": ${requestBody}}',
};

const USERS = {
  method: "GET",
  path: "/users/123",
  body: null,
  status: 200,
  responseBody: '{"id": 123, "name": "Alice"}',
};

test("accepts an answer whose keys arrive in another order", () => {
  verify(USERS, { status: 200, body: '{"name": "Alice", "id": 123}' });
});

test("rejects an answer that differs by more than key order", () => {
  assert.throws(
    () => verify(USERS, { status: 200, body: '{"id": 124, "name": "Alice"}' }),
    /GET \/users\/123 answered .*expected/,
  );
});

test("echoes a request body carrying a substitution pattern", () => {
  const exchange = { ...ITEMS, body: '{"name": "$& $1"}' };

  assert.equal(
    expectedBody(exchange),
    '{"created": true, "payload": {"name": "$& $1"}}',
  );
});

test("reports the status rather than parsing a body it never described", () => {
  assert.throws(
    () => verify(USERS, { status: 500, body: "Error: the proxy failed" }),
    /GET \/users\/123 answered 500, expected 200/,
  );
});

test("reports an answer that is not JSON with what arrived", () => {
  assert.throws(
    () => verify(USERS, { status: 200, body: "<html>not JSON</html>" }),
    /not JSON: <html>not JSON<\/html>/,
  );
});
