// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { setImmediate } from "node:timers/promises";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { load } from "../assets/data.js";
import signals from "../assets/views/signals.js";
import { report, target } from "./fixtures.js";

async function setup(t, document = report(), hash = "") {
  const html = await readFile(
    new URL("../index.html", import.meta.url),
    "utf8",
  );
  const dom = new JSDOM(html, { url: `https://example.test/${hash}` });
  const globals = {
    document: dom.window.document,
    Node: dom.window.Node,
    location: dom.window.location,
    addEventListener: dom.window.addEventListener.bind(dom.window),
    scrollTo: t.mock.fn(),
  };
  for (const [name, value] of Object.entries(globals)) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {
      configurable: true,
      writable: true,
      value,
    });
    t.after(() => {
      if (previous) Object.defineProperty(globalThis, name, previous);
      else delete globalThis[name];
    });
  }
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  t.after(() => dom.window.close());
  return dom.window;
}

test("filters columns and requirement levels without losing registry rows", async (t) => {
  const document = report([
    target(),
    target({
      id: "other",
      language: "python",
      backend: "postgresql",
      instrumented_library: "psycopg",
      signals: [
        { type: "metric", name: "db.duration", emitted: ["db.namespace"] },
      ],
    }),
  ]);
  const window = await setup(t, document);
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const select = (label, value) => {
    const node = main.querySelector(`select[aria-label="${label}"]`);
    node.value = value;
    node.dispatchEvent(new window.Event("change"));
  };
  assert.equal(main.querySelectorAll("th.col").length, 2);
  select("Language", "python");
  assert.equal(main.querySelectorAll("th.col").length, 1);
  assert.equal(main.querySelectorAll("td.cell-yes").length, 1);
  assert.equal(main.querySelectorAll("td.cell-no").length, 1);
  select("Levels", "required");
  assert.equal(main.querySelectorAll("td.cell-yes").length, 0);
  assert.equal(main.querySelectorAll("td.cell-no").length, 1);
  select("Language", "");
  select("Library", "jdbc");
  assert.equal(main.querySelectorAll("th.col").length, 1);
  select("Library", "");
  const input = main.querySelector("input");
  input.value = "postgresql";
  input.dispatchEvent(new window.Event("input"));
  assert.equal(main.querySelectorAll("th.col").length, 1);
  input.value = "no such target";
  input.dispatchEvent(new window.Event("input"));
  assert.match(main.textContent, /No targets match/);
});

test("empty reports and unknown signals give useful messages", async (t) => {
  await setup(t, report([]));
  assert.equal(
    signals(await load(), null).textContent,
    "No signals in the report.",
  );
  globalThis.fetch = async () => ({ ok: true, json: async () => report() });
  assert.match(
    signals(await load(), "metric:absent").textContent,
    /No such signal/,
  );
});

test("app loads a deep link, skips to content, and follows signal changes", async (t) => {
  const document = report([
    target({
      signals: [
        { type: "metric", name: "db.duration", emitted: ["db.system"] },
        { type: "metric", name: "db.connections", emitted: ["db.system"] },
      ],
    }),
  ]);
  const window = await setup(t, document, "#/signals/metric%3Adb.duration");
  await import("../assets/app.js");
  await setImmediate();
  const main = window.document.querySelector("main");
  assert.match(main.querySelector("h2").textContent, /db.duration/);
  assert.match(
    window.document.querySelector("#provenance").textContent,
    /1 targets/,
  );
  const content = main.firstChild;
  window.document.querySelector(".skip").click();
  assert.equal(window.document.activeElement, main);
  assert.equal(window.location.hash, "#/signals/metric%3Adb.duration");
  assert.equal(main.firstChild, content);
  assert.equal(globalThis.scrollTo.mock.callCount(), 0);

  const select = main.querySelector('select[aria-label="Signal"]');
  select.value = "metric:db.connections";
  select.dispatchEvent(new window.Event("change"));
  assert.equal(window.location.hash, "#/signals/metric%3Adb.connections");
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.match(main.querySelector("h2").textContent, /db.connections/);
  assert.equal(window.document.title, "db.connections · conformance");

  window.location.hash = "#/signals/50%";
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.ok(main.querySelector("table"));
  assert.doesNotMatch(main.textContent, /Could not render/);
});
