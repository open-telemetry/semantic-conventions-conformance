// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Runs a browser scenario: bundles its page, serves it, and opens it in
 * headless Chrome.
 *
 * Everything is served from one origin, so the page neither exports nor sends
 * its workload cross-origin. Exports under `/_otel-conformance/v1/` are
 * relayed to the runner's OTLP/HTTP bridge, which forwards them over gRPC, and
 * any other path is proxied to the mock server, so a request keeps the
 * contract's exact path and query.
 */

const http = require("node:http");

const { BRIDGE_PATH, within } = require("./page");

const SCENARIO_TIMEOUT_MILLIS = 30_000;
const CHANNEL_VARIABLE = "OTEL_CONFORMANCE_BROWSER_CHANNEL";
const EXPORT_PATH = new RegExp(`^${BRIDGE_PATH}(/v1/(traces|metrics|logs))$`);
const HTML =
  '<!doctype html><link rel="icon" href="data:,">' +
  `<script src="${BRIDGE_PATH}/page.js"></script>`;

function requireUrl(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`required environment variable is missing: ${name}`);
  }
  try {
    return new URL(value);
  } catch (error) {
    throw new Error(`${name} is not a URL: ${JSON.stringify(value)}`, {
      cause: error,
    });
  }
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

/**
 * Sends one export on to the endpoint, with the Content-Length the bridge
 * requires, and notes it in `refused` when the endpoint did not accept it.
 */
function relay(otlpEndpoint, signalPath, request, body, response, refused) {
  const target = new URL(otlpEndpoint);
  target.pathname = target.pathname.replace(/\/$/, "") + signalPath;
  const headers = { ...request.headers, host: target.host };
  delete headers["transfer-encoding"];
  headers["content-length"] = String(body.length);
  const fail = (error) => {
    refused.push(`${signalPath} failed: ${error.message}`);
    if (response.headersSent) {
      response.destroy();
      return;
    }
    response.writeHead(502, { "content-type": "text/plain" });
    response.end(`${error}\n`);
  };
  const upstream = http.request(
    target,
    { method: "POST", headers },
    (answer) => {
      if (answer.statusCode < 200 || answer.statusCode >= 300) {
        refused.push(`${signalPath} answered ${answer.statusCode}`);
      }
      answer.on("error", fail);
      response.writeHead(answer.statusCode, answer.headers);
      answer.pipe(response);
    },
  );
  upstream.on("error", fail);
  upstream.end(body);
}

/** Passes a request through to the mock server unchanged. */
function proxy(mockServer, request, response) {
  const target = new URL(request.url, mockServer);
  const upstream = http.request(target, {
    method: request.method,
    headers: { ...request.headers, host: target.host },
  });
  upstream.on("response", (answer) => {
    response.writeHead(answer.statusCode, answer.headers);
    answer.pipe(response);
  });
  upstream.on("error", (error) => {
    if (response.headersSent) {
      response.destroy();
      return;
    }
    response.writeHead(502, { "content-type": "text/plain" });
    response.end(`${error}\n`);
  });
  request.pipe(upstream);
}

/**
 * The page's origin: the page, its script, the OTLP relay, and, when there
 * is a `mockServer`, everything else proxied to it.
 */
function serve({ script, otlpEndpoint, mockServer = null, refused = [] }) {
  const server = http.createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(HTML);
      return;
    }
    if (request.method === "GET" && request.url === `${BRIDGE_PATH}/page.js`) {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end(script);
      return;
    }
    const exported = EXPORT_PATH.exec(request.url);
    if (request.method === "POST" && exported) {
      let body;
      try {
        body = await readBody(request);
      } catch (error) {
        refused.push(`${exported[1]} failed: ${error.message}`);
        response.destroy();
        return;
      }
      relay(otlpEndpoint, exported[1], request, body, response, refused);
      return;
    }
    if (mockServer && !request.url.startsWith(`${BRIDGE_PATH}/`)) {
      proxy(mockServer, request, response);
      return;
    }
    response.writeHead(404).end();
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve(server);
    });
  });
}

async function bundle(page) {
  const esbuild = require("esbuild");
  const built = await esbuild.build({
    entryPoints: [page],
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    target: "es2022",
    logLevel: "silent",
  });
  return built.outputFiles[0].contents;
}

/**
 * Chrome by default, or the channel the environment names, then Playwright's
 * own Chromium when that is not installed.
 */
async function launchBrowser(browserType) {
  const channel = process.env[CHANNEL_VARIABLE] || "chrome";
  try {
    return await browserType.launch({ channel });
  } catch (error) {
    try {
      return await browserType.launch();
    } catch (fallback) {
      throw new AggregateError(
        [error, fallback],
        `could not launch ${channel} or Playwright's Chromium`,
      );
    }
  }
}

/**
 * Opens `page`, a file that passes its workload to `exposeScenario`, calls
 * the workload with `data` and resolves with what it returned, once every
 * export it made has been accepted.
 */
async function runInBrowser({
  page,
  data = null,
  timeoutMillis = SCENARIO_TIMEOUT_MILLIS,
}) {
  if (process.env.OTEL_EXPORTER_OTLP_PROTOCOL !== "http/protobuf") {
    throw new Error("a browser exports OTLP/HTTP: declare otlp_protocol");
  }
  const otlpEndpoint = requireUrl("OTEL_EXPORTER_OTLP_ENDPOINT");
  const mockServer = process.env.MOCK_SERVER_URL
    ? requireUrl("MOCK_SERVER_URL")
    : null;
  let server;
  let browser;
  const refused = [];
  try {
    server = await serve({
      script: await bundle(page),
      otlpEndpoint,
      mockServer,
      refused,
    });
    const { chromium } = require("playwright-core");
    browser = await launchBrowser(chromium);
    const tab = await browser.newPage();
    tab.on("console", (message) =>
      console.error(`browser console.${message.type()}: ${message.text()}`),
    );
    // Logged rather than failed on: a page may raise errors on purpose. Only
    // one raised before the workload was exposed fails the run, below.
    tab.on("pageerror", (error) => console.error("browser page error:", error));
    let loaded = false;
    const failedToLoad = new Promise((_, reject) =>
      tab.once("pageerror", (error) => {
        if (!loaded) {
          reject(new Error("the page threw while loading", { cause: error }));
        }
      }),
    );
    const result = await within(
      Promise.race([
        (async () => {
          await tab.goto(`http://127.0.0.1:${server.address().port}/`);
          await tab.waitForFunction(
            () => typeof globalThis.runScenario === "function",
            null,
            { timeout: 0 },
          );
          loaded = true;
          return tab.evaluate((value) => globalThis.runScenario(value), data);
        })(),
        failedToLoad,
      ]),
      timeoutMillis,
      () =>
        loaded
          ? `the page's workload did not finish within ${timeoutMillis} ms`
          : `the page did not expose a workload within ${timeoutMillis} ms`,
    );
    if (refused.length > 0) {
      throw new Error(`exports were not accepted: ${refused.join("; ")}`);
    }
    return result;
  } finally {
    // The origin first: a page being closed can still emit, and nothing it
    // emits after its workload returned belongs in the run.
    server?.closeAllConnections();
    server?.close();
    await browser?.close();
  }
}

module.exports = { launchBrowser, runInBrowser, serve };
