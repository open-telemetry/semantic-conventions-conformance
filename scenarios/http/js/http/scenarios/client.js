// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

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
