// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  CONTENT_TYPE,
  verify,
} = require("@otel-conformance/http-test-client/response");

/** Sends the shared exchanges with browser XMLHttpRequest, without telemetry setup. */

function request(baseUrl, exchange) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(exchange.method, `${baseUrl}${exchange.path}`);
    if (exchange.body !== null) {
      xhr.setRequestHeader("content-type", CONTENT_TYPE);
    }
    xhr.addEventListener("load", () =>
      resolve({ body: xhr.responseText, status: xhr.status }),
    );
    xhr.addEventListener("error", () =>
      reject(new Error(`${exchange.method} ${exchange.path} failed`)),
    );
    xhr.addEventListener("abort", () =>
      reject(new Error(`${exchange.method} ${exchange.path} aborted`)),
    );
    xhr.addEventListener("timeout", () =>
      reject(new Error(`${exchange.method} ${exchange.path} timed out`)),
    );
    xhr.send(exchange.body);
  });
}

async function drive(baseUrl, exchanges) {
  const answered = [];
  for (const exchange of exchanges) {
    if (exchange.readiness) {
      continue;
    }
    const response = await request(baseUrl, exchange);
    verify(exchange, response);
    answered.push(`${exchange.method} ${exchange.path} -> ${response.status}`);
  }
  return answered;
}

module.exports = { drive };
