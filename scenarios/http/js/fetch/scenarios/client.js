// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  isJsonEqual,
} = require("@otel-conformance/http-test-client/json-equal");

/** Sends the shared exchanges with browser Fetch, without telemetry setup. */

async function drive(baseUrl, exchanges) {
  for (const exchange of exchanges) {
    if (exchange.readiness) {
      continue;
    }
    const response = await fetch(`${baseUrl}${exchange.path}`, {
      method: exchange.method,
      headers:
        exchange.body === null ? {} : { "content-type": "application/json" },
      body: exchange.body,
    });
    const body = await response.text();
    if (response.status !== exchange.status) {
      throw new Error(
        `${exchange.method} ${exchange.path} answered ${response.status}, expected ${exchange.status}`,
      );
    }
    const expected = exchange.responseBody.replace(
      "${requestBody}",
      exchange.body ?? "{}",
    );
    if (!isJsonEqual(JSON.parse(body), JSON.parse(expected))) {
      throw new Error(
        `${exchange.method} ${exchange.path} answered outside the contract`,
      );
    }
  }
}

module.exports = { drive };
