// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const assert = require("node:assert/strict");
const { setImmediate } = require("node:timers/promises");
const { test } = require("node:test");
const { counting } = require("../events");

test("waits until every event count is met", { timeout: 1000 }, async () => {
  const counted = counting({ "browser.web_vital": 2, "browser.console": 1 });
  let resolved = false;
  const emitted = counted.emitted().then(() => (resolved = true));

  await setImmediate();
  assert.equal(resolved, false);
  counted.processor.onEmit({ eventName: "browser.web_vital" });
  counted.processor.onEmit({ eventName: "browser.console" });
  await setImmediate();
  assert.equal(resolved, false);
  counted.processor.onEmit({ eventName: "browser.web_vital" });
  await emitted;
  assert.deepEqual(counted.seen, {
    "browser.web_vital": 2,
    "browser.console": 1,
  });
});

test("counts events emitted before waiting", { timeout: 1000 }, async () => {
  const counted = counting({ "browser.console": 1 });
  counted.processor.onEmit({ eventName: "browser.console" });
  await counted.emitted();
  assert.deepEqual(counted.seen, { "browser.console": 1 });
});

test("counts exception types separately", { timeout: 1000 }, async () => {
  const counted = counting({ "exception:TypeError": 1, "exception:Error": 1 });
  let resolved = false;
  const emitted = counted.emitted().then(() => (resolved = true));
  for (let i = 0; i < 2; i++) {
    counted.processor.onEmit({
      eventName: "exception",
      attributes: { "exception.type": "TypeError" },
    });
  }
  await setImmediate();
  assert.equal(resolved, false);
  counted.processor.onEmit({
    eventName: "exception",
    attributes: { "exception.type": "Error" },
  });
  await emitted;
  assert.deepEqual(counted.seen, {
    "exception:TypeError": 2,
    "exception:Error": 1,
  });
});

test("resolves when no events are expected", { timeout: 1000 }, async () => {
  await counting({}).emitted();
});
