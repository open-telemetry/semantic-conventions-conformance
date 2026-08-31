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
 * The shared telemetry contract checks what these requests emit. Response
 * correctness is checked centrally when the same traffic drives a server
 * scenario, not reimplemented by each client language.
 */

const { scenarioRequest, verify } = require("./contract");

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
  verify(exchange, response.status, response.body);
}

function abbreviate(value) {
  return String(value)
    .replace(/[\r\n]/g, " ")
    .slice(0, 60);
}

module.exports = { drive };
