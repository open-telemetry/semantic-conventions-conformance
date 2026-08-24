// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Checks one contract answer, the way the Node checker does.
 *
 * A browser bundle cannot use `@otel-conformance/http-test-client`, which
 * reads `contract.json` with `node:fs`, so the rules it applies are restated
 * here: a status compared exactly, and a body compared as parsed JSON, since
 * whitespace and key order are each language's JSON writer's business.
 *
 * No dependency of its own, so it runs under `node --test` here as well as in
 * the page.
 */

/** An exchange's response body with the request body inserted. */
function expectedBody(exchange) {
  // A function rather than the body itself: a string replacement reads `$&`
  // and its siblings as substitution patterns, so a body carrying one would
  // not be echoed literally.
  return exchange.responseBody.replace("${requestBody}", () =>
    exchange.body === null ? "{}" : exchange.body,
  );
}

/** Two parsed bodies compared by structure rather than by key order. */
function sameJson(actual, expected) {
  if (Array.isArray(actual) || Array.isArray(expected)) {
    return (
      Array.isArray(actual) &&
      Array.isArray(expected) &&
      actual.length === expected.length &&
      actual.every((entry, index) => sameJson(entry, expected[index]))
    );
  }
  if (
    actual === null ||
    expected === null ||
    typeof actual !== "object" ||
    typeof expected !== "object"
  ) {
    return actual === expected;
  }
  const keys = Object.keys(actual);
  return (
    keys.length === Object.keys(expected).length &&
    keys.every(
      (key) =>
        Object.prototype.hasOwnProperty.call(expected, key) &&
        sameJson(actual[key], expected[key]),
    )
  );
}

/**
 * Parses `json`, so a body that is not JSON reports what arrived.
 *
 * A body that is not JSON is a contract failure rather than a crash: it is the
 * server answering something the contract does not describe.
 */
function parse(where, json) {
  try {
    return JSON.parse(json);
  } catch {
    throw new Error(`${where} answered something that is not JSON: ${json}`);
  }
}

/**
 * Checks one answer against the exchange that describes it.
 *
 * The status first: an answer with the wrong status often carries a body the
 * contract never described, and naming the status says more than a parse
 * failure would.
 */
function verify(exchange, response) {
  const where = `${exchange.method} ${exchange.path}`;
  if (response.status !== exchange.status) {
    throw new Error(
      `${where} answered ${response.status}, expected ${exchange.status}`,
    );
  }
  const expected = parse(where, expectedBody(exchange));
  const actual = parse(where, response.body);
  if (!sameJson(actual, expected)) {
    throw new Error(
      `${where} answered ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)}`,
    );
  }
}

module.exports = { expectedBody, verify };
