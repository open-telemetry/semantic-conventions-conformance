// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Hosts the shared HTTP exchanges in Express until the driver says stop.
 *
 * The routes are declared in Express's own routing API because an
 * instrumentation reads `http.route` from the framework's routing model. Other
 * frameworks declare the same exchanges with their own API. Answering is an
 * exact lookup of the concrete request and is therefore identical for every
 * framework.
 *
 * The requests are sent by `otel-http-drive` from another process, so nothing
 * this process loads can instrument the sender and record client spans in a
 * server scenario's report. It listens on the port the driver chose and shuts
 * down when the driver closes its standard input, which is what gives the SDK
 * a chance to flush.
 */

const express = require("express");
const {
  CONTENT_TYPE,
  respond,
  scenarioPort,
} = require("@otel-conformance/http-test-client");
const { waitForEof } = require("@otel-conformance/scenario-support");

function answer(request, response) {
  // `originalUrl` rather than `path`: the contract's lookup drops the query
  // string itself, and reading the routed path here would hide a framework
  // that rewrote it.
  const { status, body } = respond(
    request.method,
    request.originalUrl,
    typeof request.body === "string" ? request.body : null,
  );
  response.status(status).type(CONTENT_TYPE).send(body);
}

function createApp() {
  const app = express();
  // Every body as text, whatever its content type: the contract echoes the
  // bytes that arrived, and parsing then re-serializing would prove only that
  // this scenario can round-trip its own JSON writer.
  app.use(express.text({ type: () => true }));

  app.get("/health", answer);
  app.get("/users/:userId", answer);
  app.post("/items", answer);
  app.get("/status/:code", answer);
  return app;
}

async function serve() {
  const server = createApp().listen(scenarioPort(), "127.0.0.1");
  await new Promise((resolve, reject) => {
    server.once("listening", resolve);
    server.once("error", reject);
  });

  try {
    await waitForEof();
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
      // The driver has stopped sending by now, so what is left are idle
      // keep-alive sockets, which `close` on its own would wait out.
      server.closeAllConnections();
    });
  }
}

module.exports = { createApp, serve };
