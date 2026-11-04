// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { isJsonEqual } = require("../src/json-equal");

test("ignores object key order at every nesting level", () => {
  assert.equal(
    isJsonEqual(
      { result: { name: "Ada", roles: [{ active: true, name: "admin" }] } },
      { result: { roles: [{ name: "admin", active: true }], name: "Ada" } },
    ),
    true,
  );
});

test("preserves array order and value types", () => {
  assert.equal(isJsonEqual({ values: [1, 2] }, { values: [2, 1] }), false);
  assert.equal(isJsonEqual({ value: 1 }, { value: "1" }), false);
});
