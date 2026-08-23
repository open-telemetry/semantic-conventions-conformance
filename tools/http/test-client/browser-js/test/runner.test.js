// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { forwardTraces } = require("../forward");

test("counts payload bytes after the collector accepts them", async () => {
  let completion;
  const payload = Buffer.from("trace");

  const exportedBytes = await forwardTraces(
    async () => {},
    payload,
    (result) => (completion = result),
  );

  assert.equal(exportedBytes, payload.length);
  assert.equal(completion, undefined);
});

test("fails completion when the collector rejects a payload", async () => {
  const collectorError = new Error("collector rejected traces");
  let completion;

  await assert.rejects(
    forwardTraces(
      async () => {
        throw collectorError;
      },
      Buffer.from("trace"),
      (result) => (completion = result),
    ),
    /collector rejected traces/,
  );

  assert.equal(completion.ok, false);
  assert.match(completion.error, /failed to forward OTLP traces/);
  assert.match(completion.error, /collector rejected traces/);
});
