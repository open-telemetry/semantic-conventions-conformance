// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/** Compares parsed JSON values without assigning meaning to object key order. */
function isJsonEqual(actual, expected) {
  if (Object.is(actual, expected)) {
    return true;
  }
  if (Array.isArray(actual) || Array.isArray(expected)) {
    return (
      Array.isArray(actual) &&
      Array.isArray(expected) &&
      actual.length === expected.length &&
      actual.every((value, index) => isJsonEqual(value, expected[index]))
    );
  }
  if (
    actual === null ||
    expected === null ||
    typeof actual !== "object" ||
    typeof expected !== "object"
  ) {
    return false;
  }
  const actualKeys = Object.keys(actual);
  const expectedKeys = Object.keys(expected);
  return (
    actualKeys.length === expectedKeys.length &&
    actualKeys.every(
      (key) =>
        Object.hasOwn(expected, key) && isJsonEqual(actual[key], expected[key]),
    )
  );
}

module.exports = { isJsonEqual };
