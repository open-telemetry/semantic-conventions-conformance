// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Shared support for Node server scenarios.
 *
 * A server scenario declares routes with the framework under test — that
 * declaration is what an instrumentation reads `http.route` from — and then
 * asks this module what to answer. Every Node framework therefore agrees on
 * the statuses and bodies without forcing its route construction into a shared
 * runtime model.
 *
 * The requests are sent by `otel-http-drive` from another process, which
 * checks every answer against the same contract.
 */

const { exchangeFor, renderResponseBody } = require("./contract");

/**
 * The port a server scenario listens on. `otel-http-drive` chooses it, which
 * is what lets different scenarios run in parallel without colliding.
 */
const PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT";

/**
 * What the contract answers to one request.
 *
 * The whole answer contract in one function, so every Node framework answers
 * identically. `requestBody` is null for a request that carried none.
 */
function respond(method, target, requestBody = null) {
  const exchange = exchangeFor(method, target);
  if (exchange === null) {
    return { status: 404, body: '{"message": "no such route"}' };
  }
  return {
    status: exchange.status,
    body: renderResponseBody(exchange, requestBody),
  };
}

/** The port the driver told this scenario to listen on. */
function scenarioPort() {
  const value = process.env[PORT_VARIABLE];
  if (!value) {
    throw new Error(
      `${PORT_VARIABLE} is not set — a server scenario is started by ` +
        "`otel-http-drive`, which chooses the port",
    );
  }
  return Number.parseInt(value, 10);
}

module.exports = { PORT_VARIABLE, respond, scenarioPort };
