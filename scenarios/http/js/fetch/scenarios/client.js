// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  CONTENT_TYPE,
  verify,
} = require("@otel-conformance/http-test-client/response");

/**
 * Sends the shared exchanges with browser Fetch, without telemetry setup, and
 * checks each answer the way the Node clients do.
 */
async function drive(baseUrl, exchanges) {
  const answered = [];
  for (const exchange of exchanges) {
    if (exchange.readiness) {
      continue;
    }
    const response = await fetch(`${baseUrl}${exchange.path}`, {
      method: exchange.method,
      headers: exchange.body === null ? {} : { "content-type": CONTENT_TYPE },
      body: exchange.body,
    });
    const body = await response.text();
    answered.push(`${exchange.method} ${exchange.path} -> ${response.status}`);
    verify(exchange, { status: response.status, body });
  }
  return answered;
}

module.exports = { drive };
