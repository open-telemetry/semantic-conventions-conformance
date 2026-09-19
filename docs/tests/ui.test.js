// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { setImmediate } from "node:timers/promises";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { load } from "../assets/data.js";
import { split } from "../assets/route.js";
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

/** Click, press and read the controls the way someone using them would. */
function driver(window, main) {
  const fire = (node, type) => node.dispatchEvent(new window.Event(type));
  const named = (selector, text) =>
    [...main.querySelectorAll(selector)].find((node) =>
      node.textContent.startsWith(text),
    );
  return {
    search(text) {
      const input = main.querySelector("input.search");
      input.value = text;
      fire(input, "input");
    },
    language: (name) => named(".pill", name).click(),
    level: (label) => named(".segment", label).click(),
    select(label, value) {
      const node = main.querySelector(`select[aria-label="${label}"]`);
      node.value = value;
      fire(node, "change");
    },
    chip: (text) => named(".chip", text).click(),
    columns: () => main.querySelectorAll("th.col").length,
    count: () => main.querySelector(".count").textContent,
    chips: () =>
      [...main.querySelectorAll(".chip")].map((chip) => chip.textContent),
    pressed: () =>
      [...main.querySelectorAll('.pill[aria-pressed="true"]')].map(
        (pill) => pill.textContent,
      ),
    picker: () => main.querySelector(".picker"),
    options: () =>
      [...main.querySelectorAll(".palette-option")].map(
        (option) => option.textContent,
      ),
    type(key) {
      const query = main.querySelector(".palette-query");
      query.value = key;
      fire(query, "input");
    },
    press(key) {
      main
        .querySelector(".palette-query")
        .dispatchEvent(
          new window.KeyboardEvent("keydown", { key, bubbles: true }),
        );
    },
  };
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
  const ui = driver(window, main);

  assert.equal(ui.columns(), 2);
  ui.language("python");
  assert.equal(ui.columns(), 1);
  assert.equal(main.querySelectorAll("td.cell-yes").length, 1);
  assert.equal(main.querySelectorAll("td.cell-no").length, 1);
  ui.level("Required only");
  assert.equal(main.querySelectorAll("td.cell-yes").length, 0);
  assert.equal(main.querySelectorAll("td.cell-no").length, 1);
  ui.language("python");
  ui.select("Library", "jdbc");
  assert.equal(ui.columns(), 1);
  ui.select("Library", "");
  ui.search("postgresql");
  assert.equal(ui.columns(), 1);
  ui.search("no such target");
  assert.match(main.textContent, /No targets match/);
});

test("language pills combine instead of replacing each other", async (t) => {
  const document = report([
    target(),
    target({ id: "py", language: "python", instrumented_library: "psycopg" }),
    target({ id: "go", language: "go", instrumented_library: "pgx" }),
  ]);
  const window = await setup(t, document);
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const ui = driver(window, main);

  // The select this replaced could show one language or all of them.
  ui.language("java");
  ui.language("go");
  assert.equal(ui.columns(), 2);
  assert.equal(ui.count(), "2 of 3 targets");
  assert.deepEqual(ui.pressed(), ["go1", "java1"]);

  // Every active filter is named, and a chip takes its own filter back off.
  assert.deepEqual(ui.chips(), ["go ✕", "java ✕", "Clear all"]);
  ui.chip("go");
  assert.equal(ui.columns(), 1);
  assert.deepEqual(ui.pressed(), ["java1"]);
  ui.chip("Clear all");
  assert.equal(ui.columns(), 3);
  assert.deepEqual(ui.chips(), []);
  assert.equal(ui.count(), "3 targets");
});

test("filters are a link, and a stale link does not filter everything away", async (t) => {
  const document = report([
    target(),
    target({ id: "py", language: "python", instrumented_library: "psycopg" }),
  ]);
  const window = await setup(t, document, "#/signals/metric%3Adb.duration");
  const main = window.document.querySelector("main");
  const data = await load();

  main.replaceChildren(
    signals(data, "metric:db.duration", new URLSearchParams()),
  );
  driver(window, main).language("python");
  assert.equal(
    window.location.hash,
    "#/signals/metric%3Adb.duration?lang=python",
  );

  // What the link above restores to, reading it back the way app.js does.
  const { path, params } = split(window.location.hash);
  assert.equal(path, "/signals/metric:db.duration");
  main.replaceChildren(signals(data, "metric:db.duration", params));
  const restored = driver(window, main);
  assert.equal(restored.columns(), 1);
  assert.deepEqual(restored.chips(), ["python ✕", "Clear all"]);

  // A language that has since left the report cannot filter to nothing.
  main.replaceChildren(
    signals(data, "metric:db.duration", new URLSearchParams("lang=cobol")),
  );
  assert.equal(driver(window, main).columns(), 2);
  assert.equal(window.location.hash, "#/signals/metric%3Adb.duration");
});

test("the distribution filter excludes what a substring search cannot", async (t) => {
  // `opentelemetry-java` matches the javaagent by its label and the java-http
  // -server library by its coordinate; the filter separates the two.
  const java = (name, label, coordinate) =>
    target({
      id: `http/java/${name}/${label}`,
      instrumented_library: name,
      instrumentation_library: coordinate,
      label,
      side: "server",
      backend: null,
      signals: [
        { type: "metric", name: "db.duration", emitted: ["db.system"] },
      ],
    });
  const document = report([
    java(
      "servlet",
      "opentelemetry-javaagent",
      "io.opentelemetry.javaagent:opentelemetry-javaagent",
    ),
    java(
      "java-http-server",
      "opentelemetry-javaagent",
      "io.opentelemetry.javaagent:opentelemetry-javaagent",
    ),
    java(
      "java-http-server",
      "opentelemetry-library",
      "io.opentelemetry.instrumentation:opentelemetry-java-http-server",
    ),
  ]);
  const window = await setup(t, document);
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const ui = driver(window, main);
  const select = main.querySelector('select[aria-label="Distribution"]');

  assert.deepEqual(
    [...select.options].map((option) => option.value),
    ["", "opentelemetry-javaagent", "opentelemetry-library"],
  );

  // The search alone drags in the library column.
  ui.search("opentelemetry-java");
  assert.equal(ui.columns(), 3);

  ui.select("Distribution", "opentelemetry-javaagent");
  assert.equal(ui.columns(), 2);
  assert.match(ui.count(), /^2 of 3 targets$/);
});

test("attribute rows link to the registry, and the band colours the language", async (t) => {
  const window = await setup(t);
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));

  const links = [...main.querySelectorAll("th.attr a")];
  assert.deepEqual(
    links.map((link) => link.textContent),
    ["db.system", "db.namespace"],
  );
  assert.equal(
    links[0].getAttribute("href"),
    "https://opentelemetry.io/docs/specs/semconv/registry/attributes/db/#db-system",
  );
  assert.equal(links[0].getAttribute("rel"), "noreferrer");

  // One language still gets a band: nothing else on the page names it.
  const bands = [...main.querySelectorAll("tr.band th.band-cell")];
  assert.deepEqual(
    bands.map((band) => band.textContent),
    ["java"],
  );
  assert.equal(bands[0].getAttribute("colspan"), "1");
  assert.match(bands[0].getAttribute("style"), /--lang-\d/);
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
  const ui = driver(window, main);
  assert.match(ui.picker().textContent, /db\.duration/);
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

  // The palette searches and groups every signal, and picking one routes.
  ui.picker().click();
  assert.deepEqual(ui.options(), [
    "metricdb.connections1",
    "metricdb.duration1",
  ]);
  ui.type("connect");
  assert.deepEqual(ui.options(), ["metricdb.connections1"]);
  ui.press("Enter");
  assert.equal(window.location.hash, "#/signals/metric%3Adb.connections");
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.match(driver(window, main).picker().textContent, /db\.connections/);
  assert.equal(window.document.title, "db.connections · conformance");
  assert.equal(globalThis.scrollTo.mock.callCount(), 1);

  // A filter change rewrites the query, which must not re-render the view.
  const kept = main.firstChild;
  driver(window, main).search("jdbc");
  assert.equal(
    window.location.hash,
    "#/signals/metric%3Adb.connections?q=jdbc",
  );
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.equal(main.firstChild, kept);

  window.location.hash = "#/signals/50%";
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.ok(main.querySelector("table"));
  assert.doesNotMatch(main.textContent, /Could not render/);
});
