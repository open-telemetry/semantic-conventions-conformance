// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  isJsonEqual,
} = require("@otel-conformance/http-test-client/json-equal");

/** Sends the shared exchanges with browser XMLHttpRequest, without telemetry setup. */

function request(baseUrl, exchange) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(exchange.method, `${baseUrl}${exchange.path}`);
    if (exchange.body !== null) {
      xhr.setRequestHeader("content-type", "application/json");
    }
    xhr.addEventListener("load", () =>
      resolve({ body: xhr.responseText, status: xhr.status }),
    );
    xhr.addEventListener("error", () =>
      reject(new Error(`${exchange.method} ${exchange.path} failed`)),
    );
    xhr.send(exchange.body);
  });
}

async function drive(baseUrl, exchanges) {
  for (const exchange of exchanges) {
    if (exchange.readiness) {
      continue;
    }
    const response = await request(baseUrl, exchange);
    if (response.status !== exchange.status) {
      throw new Error(
        `${exchange.method} ${exchange.path} answered ${response.status}, expected ${exchange.status}`,
      );
    }
    const expected = exchange.responseBody.replace(
      "${requestBody}",
      () => exchange.body ?? "{}",
    );
    if (!isJsonEqual(JSON.parse(response.body), JSON.parse(expected))) {
      throw new Error(
        `${exchange.method} ${exchange.path} answered outside the contract`,
      );
    }
  }
}

module.exports = { drive };
