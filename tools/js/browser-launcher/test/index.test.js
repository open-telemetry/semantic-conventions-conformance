// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const Module = require("node:module");
const { after, before, describe, it } = require("node:test");

function loadServe() {
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "@otel-conformance/scenario-support") {
      return { requireEnv: () => {} };
    }
    return originalLoad.call(this, request, parent, isMain);
  };
  try {
    return require("../index").serve;
  } finally {
    Module._load = originalLoad;
  }
}

/**
 * An OTLP endpoint that answers with what it was sent, and refuses anything
 * but logs the way the runner's bridge refuses a path it does not serve.
 */
function endpoint() {
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      response.statusCode = request.url === "/v1/logs" ? 200 : 404;
      response.end(
        JSON.stringify({
          method: request.method,
          url: request.url,
          type: request.headers["content-type"] ?? null,
          length: request.headers["content-length"] ?? null,
          encoding: request.headers["transfer-encoding"] ?? null,
          body: [...Buffer.concat(chunks)],
        }),
      );
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

const url = (server) => `http://127.0.0.1:${server.address().port}`;

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

describe("serve", () => {
  const refused = [];
  let otlp;
  let origin;

  before(async () => {
    otlp = await endpoint();
    origin = await loadServe()({
      script: "globalThis.loaded = true;",
      otlpEndpoint: url(otlp),
      refused,
    });
  });

  after(() => {
    for (const server of [origin, otlp]) {
      server.closeAllConnections();
      server.close();
    }
  });

  it("serves the page and its script", async () => {
    const page = await fetch(`${url(origin)}/`);
    assert.match(await page.text(), /src="\/page.js"/);
    const script = await fetch(`${url(origin)}/page.js`);
    assert.equal(await script.text(), "globalThis.loaded = true;");
  });

  it("relays an export with its type, length and bytes", async () => {
    const response = await fetch(`${url(origin)}/v1/logs`, {
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
    const answer = await postChunked(`${url(origin)}/v1/logs`, [1, 2, 3]);
    assert.equal(answer.length, "3");
    assert.equal(answer.encoding, null);
    assert.deepEqual(answer.body, [1, 2, 3]);
    assert.deepEqual(refused, []);
  });

  it("notes an export the endpoint did not accept", async () => {
    const response = await fetch(`${url(origin)}/v1/unknown`, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    assert.equal(response.status, 404);
    assert.deepEqual(refused, ["/v1/unknown answered 404"]);
  });

  it("serves nothing else", async () => {
    const response = await fetch(`${url(origin)}/favicon.ico`);
    assert.equal(response.status, 404);
  });
});

describe("serve, with the endpoint down", () => {
  const refused = [];
  let origin;

  before(async () => {
    const closed = await endpoint();
    const otlpEndpoint = url(closed);
    await new Promise((resolve) => closed.close(resolve));
    origin = await loadServe()({ script: "", otlpEndpoint, refused });
  });

  after(() => {
    origin.closeAllConnections();
    origin.close();
  });

  it("answers 502 and notes the failed export", async () => {
    const response = await fetch(`${url(origin)}/v1/logs`, {
      method: "POST",
      body: new Uint8Array([1]),
    });
    assert.equal(response.status, 502);
    assert.equal(refused.length, 1);
    assert.match(refused[0], /^\/v1\/logs failed: /);
  });
});
