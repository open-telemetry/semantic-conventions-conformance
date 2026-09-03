// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Shared support for Node client scenarios: the request contract, sent by the
 * library under test.
 *
 * Only a *client* scenario needs this: it is the sender, so the requests have
 * to leave the library under test. A server scenario is driven from outside
 * its own process by `otel-http-drive` and never sends anything.
 *
 * The shared telemetry contract checks what these requests emit.
 */

const { renderResponseBody, scenarioRequest } = require("./contract");
const { isJsonEqual } = require("./json-equal");

/**
 * Sends the runner-selected contract request at `baseUrl` through `send`.
 *
 * `send(method, url, requestBody)` is the call being measured: a client
 * scenario passes its own library, and answers with `{ status, body }`.
 * `requestBody` is null for a request that carries none.
 *
 * No health check: the runner starts the mock server a client scenario calls
 * and waits for it to answer before running the scenario at all.
 */
async function drive(baseUrl, send) {
  if (!baseUrl || !baseUrl.trim()) {
    throw new TypeError("base URL must not be blank");
  }
  const exchange = scenarioRequest();
  const response = await send(
    exchange.method,
    `${baseUrl}${exchange.path}`,
    exchange.body,
  );
  console.log(
    `${exchange.method} ${exchange.path} -> ${response.status} ` +
      `${abbreviate(response.body)}`,
  );
  verify(exchange, response);
}

/** Checks one answer against the exchange that describes it. */
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
  const actual = JSON.parse(response.body);
  if (!isJsonEqual(actual, expected)) {
    throw new Error(
      `${where} answered ${JSON.stringify(actual)}, but the contract's ` +
        `request answers ${JSON.stringify(expected)}`,
    );
  }
}

function abbreviate(value) {
  return String(value)
    .replace(/[\r\n]/g, " ")
    .slice(0, 60);
}

module.exports = { drive };
