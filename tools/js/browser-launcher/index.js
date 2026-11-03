// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Runs a browser scenario: bundles its page, serves it, and opens it in a
 * headless Chrome the machine already has.
 *
 * The page is served from one origin that also relays its OTLP exports to the
 * endpoint the runner injected. One origin is what lets the page export
 * without CORS, which the runner's bridge does not answer.
 */

const http = require("node:http");
const { requireEnv } = require("@otel-conformance/scenario-support");

const SCENARIO_TIMEOUT_MILLIS = 30_000;
const CHANNEL_VARIABLE = "OTEL_CONFORMANCE_BROWSER_CHANNEL";
const HTML =
  '<!doctype html><link rel="icon" href="data:,">' +
  '<script type="module" src="/page.js"></script>';

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

/**
 * Sends one export on to `endpoint`, with the Content-Length the bridge
 * requires, and notes it in `refused` when the endpoint did not accept it.
 */
function relay(endpoint, request, body, response, refused) {
  const target = new URL(request.url, endpoint);
  const headers = { ...request.headers, host: target.host };
  delete headers["transfer-encoding"];
  headers["content-length"] = String(body.length);
  const fail = (error) => {
    refused.push(`${request.url} failed: ${error.message}`);
    if (response.headersSent) {
      response.destroy();
      return;
    }
    response.writeHead(502, { "content-type": "text/plain" });
    response.end(`${error}\n`);
  };
  const upstream = http.request(
    target,
    { method: request.method, headers },
    (answer) => {
      if (answer.statusCode >= 400) {
        refused.push(`${request.url} answered ${answer.statusCode}`);
      }
      answer.on("error", fail);
      response.writeHead(answer.statusCode, answer.headers);
      answer.pipe(response);
    },
  );
  upstream.on("error", fail);
  upstream.end(body);
}

/** The page's origin: the page, its script and the OTLP relay. */
function serve({ script, otlpEndpoint, refused = [] }) {
  const server = http.createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(HTML);
      return;
    }
    if (request.method === "GET" && request.url === "/page.js") {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end(script);
      return;
    }
    if (request.method === "POST" && request.url.startsWith("/v1/")) {
      let body;
      try {
        body = await readBody(request);
      } catch (error) {
        refused.push(`${request.url} failed: ${error.message}`);
        response.destroy();
        return;
      }
      relay(otlpEndpoint, request, body, response, refused);
      return;
    }
    response.writeHead(404).end();
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function bundle(page) {
  const esbuild = require("esbuild");
  const built = await esbuild.build({
    entryPoints: [page],
    bundle: true,
    write: false,
    format: "esm",
    platform: "browser",
    logLevel: "silent",
  });
  return built.outputFiles[0].contents;
}

function within(promise, millis, what) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${what} timed out`)), millis);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/**
 * Opens `page` (a file exposing `runScenario` through `./page`), calls it,
 * and returns once its exports have been answered.
 */
async function runInBrowser({ page }) {
  let server;
  let browser;
  const refused = [];
  try {
    if (requireEnv("OTEL_EXPORTER_OTLP_PROTOCOL") !== "http/protobuf") {
      throw new Error("a browser exports OTLP/HTTP: declare otlp_protocol");
    }
    server = await serve({
      script: await bundle(page),
      otlpEndpoint: requireEnv("OTEL_EXPORTER_OTLP_ENDPOINT"),
      refused,
    });
    const { chromium } = require("playwright-core");
    browser = await chromium.launch({
      channel: process.env[CHANNEL_VARIABLE] || "chrome",
    });
    const tab = await browser.newPage();
    tab.on("pageerror", (error) => console.error(error));
    await tab.goto(`http://127.0.0.1:${server.address().port}/`);
    await tab.waitForFunction(() => typeof runScenario === "function");
    const result = await within(
      tab.evaluate(() => globalThis.runScenario()),
      SCENARIO_TIMEOUT_MILLIS,
      "the page's scenario",
    );
    if (refused.length > 0) {
      throw new Error(`exports were not accepted: ${refused.join("; ")}`);
    }
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    // The origin first: a page being closed can still emit, and nothing it
    // emits after its scenario returned belongs in the run.
    server?.closeAllConnections();
    server?.close();
    await browser?.close();
  }
}

module.exports = { runInBrowser, serve };
