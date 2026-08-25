// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Sends the shared HTTP exchanges with Node's built-in `http` module until
 * they are all answered.
 *
 * The mock server the runner started answers the same contract, so what the
 * scenario adds is the sending: the requests go through `http.request`, which
 * reports every status as a `response` event rather than failing on 4xx and
 * 5xx, since the contract's failing statuses are traffic to be measured like
 * any other. Its events are wrapped in a promise so one exchange is answered
 * before the next is sent.
 */

const http = require("node:http");
const {
  CONTENT_TYPE,
  USER_AGENT,
  drive,
} = require("@otel-conformance/http-test-client");
const { requireEnv } = require("@otel-conformance/scenario-support");

function send(method, url, body) {
  return new Promise((resolve, reject) => {
    const request = http.request(url, {
      method,
      headers: {
        "user-agent": USER_AGENT,
        // Only when there is one to describe, so a GET does not announce a
        // content type for a body it never sent.
        ...(body === null ? {} : { "content-type": CONTENT_TYPE }),
      },
    });
    request.on("response", (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
      response.on("end", () =>
        resolve({
          status: response.statusCode,
          body: Buffer.concat(chunks).toString("utf8"),
        }),
      );
    });
    request.on("error", reject);
    request.end(body);
  });
}

async function drivePackagedContract() {
  await drive(requireEnv("MOCK_SERVER_URL"), send);
}

module.exports = { drivePackagedContract, send };
