// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const http = require("node:http");

const grpc = require("@grpc/grpc-js");
const { build } = require("esbuild");
const { chromium } = require("playwright");
const {
  CONTENT_TYPE,
  USER_AGENT,
  requests,
} = require("@otel-conformance/http-test-client");
const { requireEnv } = require("@otel-conformance/scenario-support");
const { forwardTraces } = require("./forward");

const EXPORT_TRACES =
  "/opentelemetry.proto.collector.trace.v1.TraceService/Export";

function collect(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

function grpcClient(endpoint) {
  const url = new URL(endpoint);
  const credentials =
    url.protocol === "https:"
      ? grpc.credentials.createSsl()
      : grpc.credentials.createInsecure();
  const Client = grpc.makeGenericClientConstructor(
    {
      export: {
        path: EXPORT_TRACES,
        requestStream: false,
        responseStream: false,
        requestSerialize: (value) => value,
        requestDeserialize: (value) => value,
        responseSerialize: (value) => value,
        responseDeserialize: (value) => value,
      },
    },
    "TraceExportService",
  );
  return new Client(url.host, credentials);
}

function exportTraces(client, payload) {
  return new Promise((resolve, reject) => {
    client.export(
      payload,
      new grpc.Metadata(),
      { deadline: Date.now() + 10000 },
      (error) => (error ? reject(error) : resolve()),
    );
  });
}

async function proxyContract(request, response, mockServerUrl) {
  const body = request.method === "POST" ? await collect(request) : undefined;
  const upstream = await fetch(new URL(request.url, mockServerUrl), {
    method: request.method,
    headers: {
      "content-type": request.headers["content-type"] ?? CONTENT_TYPE,
      "user-agent": request.headers["user-agent"] ?? USER_AGENT,
    },
    body,
  });
  const payload = Buffer.from(await upstream.arrayBuffer());
  response.writeHead(upstream.status, {
    "content-type": upstream.headers.get("content-type") ?? CONTENT_TYPE,
    "content-length": payload.length,
  });
  response.end(payload);
}

function page(title) {
  const configuration = JSON.stringify({
    doneEndpoint: "/__done",
    tracesEndpoint: "/v1/traces",
    requests: requests(),
  }).replaceAll("<", "\\u003c");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <script>window.__OTEL_HTTP_CONFORMANCE__ = ${configuration};</script>
  <script src="/app.js"></script>
</head>
<body></body>
</html>`;
}

async function runBrowserScenario({ entry, title }) {
  const bundle = await build({
    entryPoints: [entry],
    bundle: true,
    platform: "browser",
    format: "iife",
    target: "chrome120",
    write: false,
  });
  const script = bundle.outputFiles[0].contents;
  const collector = grpcClient(requireEnv("OTEL_EXPORTER_OTLP_ENDPOINT"));
  const mockServerUrl = requireEnv("MOCK_SERVER_URL");
  let complete;
  let exportedBytes = 0;
  const completion = new Promise((resolve) => {
    complete = resolve;
  });

  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, "http://127.0.0.1");
      if (request.method === "GET" && url.pathname === "/") {
        const payload = Buffer.from(page(title));
        response.writeHead(200, {
          "content-type": "text/html; charset=utf-8",
          "content-length": payload.length,
        });
        response.end(payload);
      } else if (request.method === "GET" && url.pathname === "/app.js") {
        response.writeHead(200, {
          "content-type": "application/javascript; charset=utf-8",
          "content-length": script.length,
        });
        response.end(script);
      } else if (request.method === "POST" && url.pathname === "/v1/traces") {
        const payload = await collect(request);
        exportedBytes += await forwardTraces(
          (value) => exportTraces(collector, value),
          payload,
          complete,
        );
        response.writeHead(200, { "content-type": "application/x-protobuf" });
        response.end();
      } else if (request.method === "POST" && url.pathname === "/__done") {
        complete(JSON.parse((await collect(request)).toString("utf8")));
        response.writeHead(204);
        response.end();
      } else if (url.pathname === "/favicon.ico") {
        response.writeHead(204);
        response.end();
      } else {
        await proxyContract(request, response, mockServerUrl);
      }
    } catch (error) {
      console.error(error);
      response.writeHead(500, { "content-type": "text/plain" });
      response.end(error instanceof Error ? error.stack : String(error));
    }
  });

  await new Promise((resolve, reject) => {
    server.listen(0, "127.0.0.1", resolve);
    server.once("error", reject);
  });
  const address = server.address();
  let browser;
  let browserPage;

  try {
    browser = await chromium.launch({ headless: true });
    browserPage = await browser.newPage();
    browserPage.on("console", (message) =>
      console.log(`[browser:${message.type()}] ${message.text()}`),
    );
    browserPage.on("pageerror", (error) =>
      complete({ ok: false, error: error.stack ?? error.message }),
    );
    await browserPage.goto(`http://127.0.0.1:${address.port}/`, {
      waitUntil: "load",
    });
    let timeout;
    const result = await Promise.race([
      completion,
      new Promise(
        (resolve) =>
          (timeout = setTimeout(
            () => resolve({ ok: false, error: "browser scenario timed out" }),
            30000,
          )),
      ),
    ]);
    clearTimeout(timeout);
    if (!result.ok) {
      throw new Error(result.error ?? "browser scenario failed");
    }
    if (exportedBytes === 0) {
      throw new Error("browser scenario exported no OTLP trace payloads");
    }
  } finally {
    await browserPage?.close();
    await browser?.close();
    collector.close();
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
}

module.exports = { runBrowserScenario };
