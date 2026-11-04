// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { after, test } = require("node:test");
const { drive } = require("..");

const original = Object.getOwnPropertyDescriptor(globalThis, "XMLHttpRequest");
after(() => {
  if (original) {
    Object.defineProperty(globalThis, "XMLHttpRequest", original);
  } else {
    delete globalThis.XMLHttpRequest;
  }
});

const exchange = {
  method: "GET",
  path: "/users/123",
  body: null,
  status: 200,
  responseBody: '{"id":123}',
};

function answerWith(event) {
  globalThis.XMLHttpRequest = class extends EventTarget {
    open(method, target) {
      assert.equal(method, exchange.method);
      assert.equal(target, `http://localhost${exchange.path}`);
    }
    send(body) {
      assert.equal(body, exchange.body);
      this.status = 200;
      this.responseText = exchange.responseBody;
      this.dispatchEvent(new Event(event));
    }
  };
}

test("checks a loaded response against the contract", async () => {
  answerWith("load");
  assert.deepEqual(await drive("http://localhost", [exchange]), [
    "GET /users/123 -> 200",
  ]);
});

for (const [event, reason] of [
  ["error", "failed"],
  ["abort", "aborted"],
  ["timeout", "timed out"],
]) {
  test(
    `rejects ${event} with the request method and path`,
    { timeout: 1000 },
    async () => {
      answerWith(event);
      await assert.rejects(drive("http://localhost", [exchange]), {
        message: `GET /users/123 ${reason}`,
      });
    },
  );
}
