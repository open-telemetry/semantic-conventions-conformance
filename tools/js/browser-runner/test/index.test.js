// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const path = require("node:path");
const test = require("node:test");

const grpc = require("@grpc/grpc-js");

const { launchBrowser, runBrowserScenario } = require("../index");

const TRACE_EXPORT_PATH =
  "/opentelemetry.proto.collector.trace.v1.TraceService/Export";

const service = {
  export: {
    path: TRACE_EXPORT_PATH,
    requestStream: false,
    responseStream: false,
    requestSerialize: (value) => value,
    requestDeserialize: (value) => value,
    responseSerialize: (value) => value,
    responseDeserialize: (value) => value,
  },
};

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
}

function close(server) {
  server.closeAllConnections?.();
  return new Promise((resolve) => server.close(resolve));
}

function bind(server) {
  return new Promise((resolve, reject) => {
    server.bindAsync(
      "127.0.0.1:0",
      grpc.ServerCredentials.createInsecure(),
      (error, port) => (error ? reject(error) : resolve(port)),
    );
  });
}

test("falls back to Playwright's managed Chromium", async () => {
  const launches = [];
  const managed = { close() {} };
  const browserType = {
    async launch(options) {
      launches.push(options);
      if (options.channel === "chrome") {
        throw new Error("Chrome is not installed");
      }
      return managed;
    },
  };

  assert.equal(await launchBrowser(browserType), managed);
  assert.deepEqual(launches, [
    { channel: "chrome", headless: true },
    { headless: true },
  ]);
});

test("validates the mock URL before constructing a collector client", async () => {
  const original = Object.getOwnPropertyDescriptor(
    grpc,
    "makeGenericClientConstructor",
  );
  let constructed = false;
  const previous = {
    mock: process.env.MOCK_SERVER_URL,
    endpoint: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  };
  Object.defineProperty(grpc, "makeGenericClientConstructor", {
    configurable: true,
    value: () => {
      constructed = true;
    },
  });
  process.env.MOCK_SERVER_URL = "not a URL";
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4317";
  try {
    await assert.rejects(
      runBrowserScenario({ entrypoint: "unused.js", exchanges: [] }),
      /MOCK_SERVER_URL/,
    );
  } finally {
    Object.defineProperty(grpc, "makeGenericClientConstructor", original);
    process.env.MOCK_SERVER_URL = previous.mock;
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = previous.endpoint;
  }
  assert.equal(constructed, false);
});

test("proxies contract traffic and forwards browser OTLP protobuf", async () => {
  const mock = http.createServer((request, response) => {
    assert.equal(request.url, "/example");
    response.end("contract response");
  });
  await listen(mock);
  const mockPort = mock.address().port;

  let telemetry;
  const collector = new grpc.Server();
  collector.addService(service, {
    export(call, callback) {
      telemetry = call.request;
      callback(null, Buffer.alloc(0));
    },
  });
  const collectorPort = await bind(collector);
  collector.start();

  const previous = {
    mock: process.env.MOCK_SERVER_URL,
    endpoint: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  };
  process.env.MOCK_SERVER_URL = `http://127.0.0.1:${mockPort}`;
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT = `http://127.0.0.1:${collectorPort}`;
  try {
    await runBrowserScenario({
      entrypoint: path.join(__dirname, "fixtures", "browser.js"),
      exchanges: [],
    });
  } finally {
    process.env.MOCK_SERVER_URL = previous.mock;
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = previous.endpoint;
    await close(mock);
    collector.forceShutdown();
  }
  assert.deepEqual(telemetry, Buffer.from([1, 2, 3]));
});
