// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Hosts the shared HTTP exchanges on Node's built-in HTTP server until the
 * driver says stop.
 *
 * No framework and so no routing model: one handler answers every request by
 * its concrete method and target, which is why a run here records no
 * `http.route`. The answering itself is the shared lookup every framework
 * scenario performs once its own routing has matched.
 *
 * The requests are sent by `otel-http-drive` from another process, so nothing
 * this process loads can instrument the sender and record client spans in a
 * server scenario's report. It listens on the port the driver chose and shuts
 * down when the driver closes its standard input, which is what gives the SDK
 * a chance to flush.
 */

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
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      // `respond` documents `null` as the value for a request with no body.
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
      // Idle keep-alive sockets close with the server, but a connection still
      // in flight would hold `close` open, and a scenario that does not exit
      // is a scenario the runner waits out.
      server.closeAllConnections();
    });
  }
}

module.exports = { serve };
