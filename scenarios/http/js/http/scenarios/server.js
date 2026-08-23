// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const http = require("node:http");
const {
  CONTENT_TYPE,
  respond,
  scenarioPort,
} = require("@otel-conformance/http-test-client");
const { waitForEof } = require("@otel-conformance/scenario-support");

async function serve() {
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => {
      const body = chunks.length
        ? Buffer.concat(chunks).toString("utf8")
        : null;
      const answer = respond(request.method, request.url, body);
      response.writeHead(answer.status, { "content-type": CONTENT_TYPE });
      response.end(answer.body);
    });
  });
  await new Promise((resolve, reject) => {
    server.listen(scenarioPort(), "127.0.0.1", resolve);
    server.once("error", reject);
  });
  try {
    await waitForEof();
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
      server.closeAllConnections();
    });
  }
}

module.exports = { serve };
