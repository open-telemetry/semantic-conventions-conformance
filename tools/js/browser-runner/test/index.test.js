// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const path = require("node:path");
const { after, before, describe, it } = require("node:test");

const { launchBrowser, runInBrowser, serve } = require("..");

/**
 * A mock OTLP endpoint that echoes what it was sent, answering `status`. The
 * real bridge accepts traces, metrics and logs.
 */
function endpoint(status = 200) {
  const received = [];
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const seen = {
        method: request.method,
        url: request.url,
        type: request.headers["content-type"] ?? null,
        length: request.headers["content-length"] ?? null,
        encoding: request.headers["transfer-encoding"] ?? null,
        body: [...Buffer.concat(chunks)],
      };
      received.push(seen);
      response.statusCode = status;
      response.end(JSON.stringify(seen));
    });
  });
  server.received = received;
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

/** A mock server that answers every request with its own target. */
function mockServer() {
  const server = http.createServer((request, response) => {
    response.end(`${request.method} ${request.url}`);
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

/**
 * A server that takes a request and never answers it. `requested` resolves
 * when the request arrives and `closed` when its connection is dropped.
 */
function hanging() {
  let requested;
  let closed;
  const server = http.createServer((request, response) => {
    response.on("close", closed);
    requested();
  });
  server.requested = new Promise((resolve) => (requested = resolve));
  server.closed = new Promise((resolve) => (closed = resolve));
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

/** Rejects with `what` if `promise` has not settled within a few seconds. */
function soon(promise, what) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${what} timed out`)), 5_000);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

const url = (server) => `http://127.0.0.1:${server.address().port}`;

function closeAll(...servers) {
  for (const server of servers) {
    server.closeAllConnections();
    server.close();
  }
}

/** Posts `body` in chunks, with no Content-Length. */
function postChunked(target, body) {
  return new Promise((resolve, reject) => {
    const request = http.request(target, { method: "POST" }, (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () =>
        resolve(JSON.parse(Buffer.concat(chunks).toString())),
      );
    });
    request.on("error", reject);
    for (const byte of body) {
      request.write(Buffer.from([byte]));
    }
    request.end();
  });
}

async function withEnv(variables, callback) {
  const previous = {};
  for (const [name, value] of Object.entries(variables)) {
    previous[name] = process.env[name];
    process.env[name] = value;
  }
  try {
    return await callback();
  } finally {
    for (const [name, value] of Object.entries(previous)) {
      if (value === undefined) {
        delete process.env[name];
      } else {
        process.env[name] = value;
      }
    }
  }
}

const fixture = (name) => path.join(__dirname, "fixtures", `${name}.js`);

describe("serve", () => {
  const refused = [];
  let otlp;
  let mock;
  let origin;

  before(async () => {
    otlp = await endpoint();
    mock = await mockServer();
    origin = await serve({
      script: "globalThis.loaded = true;",
      otlpEndpoint: new URL(url(otlp)),
      mockServer: new URL(url(mock)),
      refused,
    });
  });

  after(() => closeAll(origin, otlp, mock));

  it("serves the page and its script", async () => {
    const page = await fetch(`${url(origin)}/`);
    assert.match(await page.text(), /src="\/_otel-conformance\/page.js"/);
    const script = await fetch(`${url(origin)}/_otel-conformance/page.js`);
    assert.equal(await script.text(), "globalThis.loaded = true;");
  });

  it("relays an export with its type, length and bytes", async () => {
    const response = await fetch(`${url(origin)}/_otel-conformance/v1/logs`, {
      method: "POST",
      headers: { "content-type": "application/x-protobuf" },
      body: new Uint8Array([1, 2, 3]),
    });
    assert.deepEqual(await response.json(), {
      method: "POST",
      url: "/v1/logs",
      type: "application/x-protobuf",
      length: "3",
      encoding: null,
      body: [1, 2, 3],
    });
    assert.deepEqual(refused, []);
  });

  it("relays a chunked export with a Content-Length", async () => {
    const answer = await postChunked(
      `${url(origin)}/_otel-conformance/v1/traces`,
      [1, 2, 3],
    );
    assert.equal(answer.url, "/v1/traces");
    assert.equal(answer.length, "3");
    assert.equal(answer.encoding, null);
    assert.deepEqual(answer.body, [1, 2, 3]);
    assert.deepEqual(refused, []);
  });

  it("proxies any other request to the mock server with its query", async () => {
    const response = await fetch(`${url(origin)}/users/123?fields=name`);
    assert.equal(await response.text(), "GET /users/123?fields=name");
  });

  it("proxies nothing else under its own path", async () => {
    const response = await fetch(`${url(origin)}/_otel-conformance/v1/other`, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    assert.equal(response.status, 404);
    assert.deepEqual(refused, []);
  });
});

describe("serve, with the endpoint refusing", () => {
  const refused = [];
  let otlp;
  let origin;

  before(async () => {
    otlp = await endpoint(500);
    origin = await serve({
      script: "",
      otlpEndpoint: new URL(url(otlp)),
      refused,
    });
  });

  after(() => closeAll(origin, otlp));

  it("passes the answer back and notes the refused export", async () => {
    const response = await fetch(`${url(origin)}/_otel-conformance/v1/logs`, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    assert.equal(response.status, 500);
    assert.deepEqual(refused, ["/v1/logs answered 500"]);
  });
});

describe("serve, with the endpoint down", () => {
  const refused = [];
  let origin;

  before(async () => {
    const closed = await endpoint();
    const otlpEndpoint = new URL(url(closed));
    await new Promise((resolve) => closed.close(resolve));
    origin = await serve({ script: "", otlpEndpoint, refused });
  });

  after(() => closeAll(origin));

  it("answers 502 and notes the failed export", async () => {
    const response = await fetch(`${url(origin)}/_otel-conformance/v1/logs`, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    assert.equal(response.status, 502);
    assert.equal(refused.length, 1);
    assert.match(refused[0], /^\/v1\/logs failed: /);
  });
});

describe("serve, with nothing answering", () => {
  let otlp;
  let mock;
  let origin;

  before(async () => {
    otlp = await hanging();
    mock = await hanging();
    origin = await serve({
      script: "",
      otlpEndpoint: new URL(url(otlp)),
      mockServer: new URL(url(mock)),
    });
  });

  after(() => closeAll(origin, otlp, mock));

  /** Requests `path`, then gives up once `server` has it. */
  async function abandon(path, server, init = {}) {
    const controller = new AbortController();
    const answered = fetch(`${url(origin)}${path}`, {
      ...init,
      signal: controller.signal,
    }).catch(() => {});
    await soon(server.requested, "the request");
    controller.abort();
    await answered;
  }

  it("cancels an export once nothing waits for it", async () => {
    await abandon("/_otel-conformance/v1/logs", otlp, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    await soon(otlp.closed, "cancelling the export");
  });

  it("cancels a proxied request once nothing waits for it", async () => {
    await abandon("/users/123", mock);
    await soon(mock.closed, "cancelling the request");
  });
});

describe("launchBrowser", () => {
  it("falls back to Playwright's Chromium", async () => {
    const launches = [];
    const managed = {};
    const browserType = {
      async launch(options) {
        launches.push(options);
        if (options?.channel) {
          throw new Error("Chrome is not installed");
        }
        return managed;
      },
    };
    assert.equal(await launchBrowser(browserType), managed);
    assert.deepEqual(launches, [{ channel: "chrome" }, undefined]);
  });

  it("keeps both reasons when neither launches", async () => {
    const browserType = {
      async launch(options) {
        throw new Error(options ? "no Chrome" : "no Chromium");
      },
    };
    await assert.rejects(launchBrowser(browserType), (error) => {
      assert.ok(error instanceof AggregateError);
      assert.deepEqual(
        error.errors.map(({ message }) => message),
        ["no Chrome", "no Chromium"],
      );
      return true;
    });
  });
});

describe("runInBrowser", () => {
  let mock;

  before(async () => {
    mock = await mockServer();
  });

  after(() => closeAll(mock));

  async function run(otlp, page, options = {}) {
    return withEnv(
      {
        MOCK_SERVER_URL: url(mock),
        OTEL_EXPORTER_OTLP_ENDPOINT:
          typeof otlp === "string" ? otlp : url(otlp),
        OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf",
      },
      () => runInBrowser({ page: fixture(page), ...options }),
    );
  }

  it("runs the workload against the mock server and relays its export", async () => {
    const otlp = await endpoint();
    try {
      const result = await run(otlp, "exports", {
        data: { path: "/items?id=1" },
      });
      assert.deepEqual(result, { answer: "GET /items?id=1", exported: 200 });
      assert.deepEqual(
        otlp.received.map(({ url, body }) => ({ url, body })),
        [{ url: "/v1/traces", body: [1, 2, 3] }],
      );
    } finally {
      closeAll(otlp);
    }
  });

  it("fails when the endpoint answers an export with an error", async () => {
    const otlp = await endpoint(500);
    try {
      await assert.rejects(
        run(otlp, "exports", { data: { path: "/" } }),
        /exports were not accepted: \/v1\/traces answered 500/,
      );
    } finally {
      closeAll(otlp);
    }
  });

  it("fails when the endpoint is unreachable", async () => {
    const closed = await endpoint();
    const otlp = url(closed);
    await new Promise((resolve) => closed.close(resolve));
    await assert.rejects(
      run(otlp, "exports", { data: { path: "/" } }),
      /exports were not accepted: \/v1\/traces failed: /,
    );
  });

  it("lets go of an endpoint that never answers", async () => {
    const otlp = await hanging();
    try {
      await assert.rejects(
        run(otlp, "exports", { data: { path: "/" }, timeoutMillis: 1_000 }),
        /the page's workload did not finish within 1000 ms/,
      );
      await soon(otlp.closed, "cancelling the export");
    } finally {
      closeAll(otlp);
    }
  });

  it("fails with the page's own error when its bundle throws", async () => {
    const otlp = await endpoint();
    try {
      await assert.rejects(run(otlp, "throws"), (error) => {
        assert.equal(error.message, "the page threw while loading");
        assert.match(error.cause.message, /failed at the top level/);
        return true;
      });
    } finally {
      closeAll(otlp);
    }
  });

  it("fails when the workload does not finish in time", async () => {
    const otlp = await endpoint();
    try {
      await assert.rejects(
        run(otlp, "hangs", { timeoutMillis: 1_000 }),
        /the page's workload did not finish within 1000 ms/,
      );
    } finally {
      closeAll(otlp);
    }
  });

  it("fails when the page never exposes a workload", async () => {
    const otlp = await endpoint();
    try {
      await assert.rejects(
        run(otlp, "no-workload", { timeoutMillis: 1_000 }),
        /the page did not expose a workload within 1000 ms/,
      );
    } finally {
      closeAll(otlp);
    }
  });

  it("refuses a gRPC endpoint before anything starts", async () => {
    await withEnv({ OTEL_EXPORTER_OTLP_PROTOCOL: "grpc" }, () =>
      assert.rejects(
        runInBrowser({ page: fixture("exports") }),
        /declare otlp_protocol/,
      ),
    );
  });
});
