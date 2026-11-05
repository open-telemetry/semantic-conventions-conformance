// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Checking an answer against the exchange that describes it.
 *
 * Kept apart from `contract.js`, which reads `contract.yaml` from disk, so a
 * browser scenario can bundle the same check as the Node clients use.
 */

const { isJsonEqual } = require("./json-equal");

/** Every route answers JSON, so a scenario has one content type rather than a rule per route. */
const CONTENT_TYPE = "application/json";

/** An exchange's response body with the request body inserted. */
function renderResponseBody(exchange, requestBody) {
  // A function rather than the body itself: a string replacement reads `$&`
  // and its siblings as substitution patterns, so a body carrying one would
  // not be echoed literally.
  return exchange.responseBody.replace("${requestBody}", () =>
    requestBody ? requestBody : "{}",
  );
}

/** Throws unless `{ status, body }` is what the contract answers `exchange` with. */
function verify(exchange, response) {
  const where = `${exchange.method} ${exchange.path}`;
  if (response.status !== exchange.status) {
    throw new Error(
      `${where} answered ${response.status}, but the contract's request ` +
        `answers ${exchange.status}`,
    );
  }

  // Parsed, not compared as text: whitespace and key order are a language's
  // choice of JSON writer, and neither is part of the contract.
  const expected = JSON.parse(renderResponseBody(exchange, exchange.body));
  let actual;
  try {
    actual = JSON.parse(response.body);
  } catch (error) {
    throw new Error(
      `${where} answered ${JSON.stringify(String(response.body).slice(0, 60))}, ` +
        "which is not JSON",
      { cause: error },
    );
  }
  if (!isJsonEqual(actual, expected)) {
    throw new Error(
      `${where} answered ${JSON.stringify(actual)}, but the contract's ` +
        `request answers ${JSON.stringify(expected)}`,
    );
  }
}

module.exports = { CONTENT_TYPE, renderResponseBody, verify };
