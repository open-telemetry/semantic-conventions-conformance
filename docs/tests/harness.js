// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";
import { report } from "./fixtures.js";

export async function setup(t, document = report(), hash = "") {
  const html = await readFile(
    new URL("../index.html", import.meta.url),
    "utf8",
  );
  const dom = new JSDOM(html, { url: `https://example.test/${hash}` });
  const globals = {
    document: dom.window.document,
    Node: dom.window.Node,
    CSS: dom.window.CSS,
    location: dom.window.location,
    history: dom.window.history,
    navigator: dom.window.navigator,
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
