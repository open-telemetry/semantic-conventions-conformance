// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Starts a browser workload and forwards its OTLP/HTTP protobuf exports to
 * the conformance runner's OTLP/gRPC collector.
 *
 * A browser cannot speak OTLP/gRPC directly. The bridge gives its bundled
 * page a same-origin OTLP/HTTP endpoint, then carries the protobuf request
 * unchanged over gRPC. Every path except the bridge's own endpoints proxies
 * unchanged to the runner's mock server, so Fetch observes the contract's
 * exact paths without a cross-origin preflight.
 */

const http = require("node:http");
const { URL } = require("node:url");

const grpc = require("@grpc/grpc-js");
const { chromium } = require("@playwright/test");
const esbuild = require("esbuild");

const TRACE_EXPORT_PATH =
  "/opentelemetry.proto.collector.trace.v1.TraceService/Export";
const BRIDGE_PATH = "/_otel-conformance";

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`required environment variable is missing: ${name}`);
  }
  return value;
}

function requireUrl(name) {
  const value = requireEnv(name);
  try {
    const url = new URL(value);
    if (!url.host) {
      throw new Error("URL must include a host");
    }
    return url;
  } catch (error) {
    throw new Error(`required environment variable is not a URL: ${name}`, {
      cause: error,
    });
  }
}

function grpcTraceClient(endpoint) {
  const address = endpoint.host;
  const TraceService = grpc.makeGenericClientConstructor(
    {
      export: {
        path: TRACE_EXPORT_PATH,
        requestStream: false,
        responseStream: false,
        requestSerialize: (value) => value,
        requestDeserialize: (value) => value,
        responseSerialize: (value) => value,
        responseDeserialize: (value) => value,
      },
    },
    "TraceService",
  );
  return new TraceService(address, grpc.credentials.createInsecure());
}

function forward(client, payload) {
  return new Promise((resolve, reject) => {
    client.export(payload, (error) => (error ? reject(error) : resolve()));
  });
}

function read(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

function proxy(request, response, mockServer) {
  const target = new URL(request.url, mockServer);
  const upstream = http.request(target, {
    method: request.method,
    headers: { ...request.headers, host: target.host },
  });
  upstream.on("response", (upstreamResponse) => {
    response.writeHead(upstreamResponse.statusCode, upstreamResponse.headers);
    upstreamResponse.pipe(response);
  });
  upstream.on("error", (error) => {
    response.writeHead(502, { "content-type": "text/plain" });
    response.end(error.message);
  });
  request.pipe(upstream);
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve(server.address().port);
    });
  });
}

function close(server) {
  server.closeAllConnections?.();
  return new Promise((resolve, reject) =>
    server.close((error) => (error ? reject(error) : resolve())),
  );
}

/** Prefer a locally installed Chrome, then Playwright's managed Chromium. */
async function launchBrowser(browserType = chromium) {
  try {
    return await browserType.launch({ channel: "chrome", headless: true });
  } catch {
    return browserType.launch({ headless: true });
  }
}

async function bundle(entrypoint) {
  const result = await esbuild.build({
    bundle: true,
    entryPoints: [entrypoint],
    format: "iife",
    platform: "browser",
    target: "es2022",
    write: false,
  });
  return result.outputFiles[0].text;
}

/** Runs one bundled browser workload against the shared HTTP contract. */
async function runBrowserScenario({ entrypoint, exchanges }) {
  const mockServer = requireUrl("MOCK_SERVER_URL");
  const collectorEndpoint = requireUrl("OTEL_EXPORTER_OTLP_ENDPOINT");
  const collector = grpcTraceClient(collectorEndpoint);
  let server;
  let browser;
  try {
    const script = await bundle(entrypoint);
    let bridgeUrl;
    server = http.createServer(async (request, response) => {
      try {
        if (request.method === "GET" && request.url === "/") {
          response.writeHead(200, {
            "content-type": "text/html; charset=utf-8",
          });
          response.end(
            `<!doctype html><link rel="icon" href="data:,"><script src="${BRIDGE_PATH}/scenario.js"></script>`,
          );
          return;
        }
        if (
          request.method === "GET" &&
          request.url === `${BRIDGE_PATH}/scenario.js`
        ) {
          response.writeHead(200, {
            "content-type": "text/javascript; charset=utf-8",
          });
          response.end(
            `window.__otelConformance = ${JSON.stringify({
              baseUrl: bridgeUrl,
              traceExporterUrl: `${bridgeUrl}${BRIDGE_PATH}/v1/traces`,
              exchanges,
            })};\n${script}`,
          );
          return;
        }
        if (
          request.method === "POST" &&
          request.url === `${BRIDGE_PATH}/v1/traces`
        ) {
          await forward(collector, await read(request));
          response.writeHead(200);
          response.end();
          return;
        }
        proxy(request, response, mockServer);
      } catch (error) {
        response.writeHead(500, { "content-type": "text/plain" });
        response.end(error instanceof Error ? error.stack : String(error));
      }
    });
    const port = await listen(server);
    bridgeUrl = `http://127.0.0.1:${port}`;
    browser = await launchBrowser();
    const page = await browser.newPage();
    await page.goto(bridgeUrl);
    await page.waitForFunction(
      () => window.__otelConformanceResult !== undefined,
    );
    const result = await page.evaluate(() => window.__otelConformanceResult);
    if (!result.ok) {
      throw new Error(result.error);
    }
  } finally {
    try {
      await browser?.close();
    } finally {
      try {
        if (server?.listening) {
          await close(server);
        }
      } finally {
        collector.close();
      }
    }
  }
}

module.exports = { launchBrowser, runBrowserScenario };
