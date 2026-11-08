// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { setup } from "./harness.js";
import { setImmediate } from "node:timers/promises";
import { test } from "node:test";
import { load } from "../assets/data.js";
import { split } from "../assets/route.js";
import signals, { dispose } from "../assets/views/signals.js";
import { report, target } from "./fixtures.js";

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

test("column headers name the library, its qualifier, and the distribution", async (t) => {
  const jdbc = (label) =>
    target({
      id: `database/java/mariadb/jdbc/${label}`,
      label,
      signals: [
        { type: "metric", name: "db.duration", emitted: ["db.system"] },
      ],
    });
  const window = await setup(
    t,
    report([jdbc("opentelemetry-javaagent"), jdbc("opentelemetry-library")]),
  );
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));

  const headers = [...main.querySelectorAll("th.col a")];
  assert.deepEqual(
    headers.map((header) =>
      [...header.children].map((part) => part.textContent),
    ),
    [
      ["jdbc", "mariadb · otel-javaagent"],
      ["jdbc", "mariadb · otel-library"],
    ],
  );
  assert.ok(headers[0].querySelector(".secondary"));
  assert.match(headers[1].getAttribute("title"), /opentelemetry-library/);
});

test("native column headers use a short secondary line and retain the full accessible name", async (t) => {
  const window = await setup(
    t,
    report([
      target({
        instrumented_library: "elasticsearch-java",
        backend: "elasticsearch",
        label: "native-instrumentation",
      }),
    ]),
  );
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const header = main.querySelector("th.col a");
  assert.equal(header.querySelector("b").textContent, "elasticsearch-java");
  assert.equal(header.querySelector(".secondary").textContent, "native");
  assert.match(header.getAttribute("title"), /native-instrumentation/);
  assert.equal(header.getAttribute("aria-label"), header.getAttribute("title"));
});

test("scroll rail initializes and follows window resizing without ResizeObserver", async (t) => {
  const window = await setup(t);
  assert.equal(typeof globalThis.ResizeObserver, "undefined");
  t.mock.timers.enable({ apis: ["setTimeout"] });

  const view = signals(await load(), null);
  const frame = view.querySelector(".scroll-frame");
  const scroller = frame.querySelector(".scroller");
  const rail = frame.querySelector(".scroll-rail");
  Object.defineProperties(scroller, {
    scrollWidth: { value: 1000 },
    clientWidth: { value: 400, writable: true },
  });
  Object.defineProperty(scroller.querySelector("th.attr"), "offsetWidth", {
    value: 200,
  });
  assert.equal(rail.firstElementChild.style.width, "");

  window.document.querySelector("main").replaceChildren(view);
  t.mock.timers.tick(0);

  assert.equal(rail.firstElementChild.style.width, "1000px");
  assert.equal(frame.style.getPropertyValue("--pinned-w"), "200px");
  assert.equal(frame.classList.contains("fits"), false);
  assert.equal(frame.classList.contains("more-left"), false);
  assert.equal(frame.classList.contains("more-right"), true);

  scroller.clientWidth = 1200;
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(frame.classList.contains("fits"), true);
  assert.equal(frame.classList.contains("more-right"), false);

  scroller.clientWidth = 400;
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(frame.classList.contains("fits"), false);
  assert.equal(frame.classList.contains("more-right"), true);
});

for (const observed of [false, true]) {
  test(`headers stick within one-third of the viewport regardless of horizontal overflow, ${observed ? "with" : "without"} ResizeObserver`, async (t) => {
    const window = await setup(t);
    Object.defineProperty(window, "CSS", {
      configurable: true,
      value: { supports: () => true },
    });
    t.mock.timers.enable({ apis: ["setTimeout"] });
    let observer;
    if (observed) {
      const previous = Object.getOwnPropertyDescriptor(
        globalThis,
        "ResizeObserver",
      );
      Object.defineProperty(globalThis, "ResizeObserver", {
        configurable: true,
        value: class {
          constructor(callback) {
            this.callback = callback;
            this.observe = t.mock.fn();
            this.disconnect = t.mock.fn();
            observer = this;
          }
        },
      });
      t.after(() => {
        if (previous)
          Object.defineProperty(globalThis, "ResizeObserver", previous);
        else delete globalThis.ResizeObserver;
      });
    }

    const view = signals(await load(), null);
    const frame = view.querySelector(".scroll-frame");
    const scroller = frame.querySelector(".scroller");
    const table = scroller.firstElementChild;
    const header = table.querySelector("thead");
    const rail = frame.querySelector(".scroll-rail");
    const viewport = window.document.documentElement;
    Object.defineProperties(scroller, {
      scrollWidth: { value: 1000 },
      clientWidth: { value: 1000, writable: true },
    });
    let headerHeight = 300;
    let tableHeight = 1200;
    Object.defineProperty(viewport, "clientHeight", {
      value: 900,
      writable: true,
    });
    t.mock.method(table, "getBoundingClientRect", () => ({
      height: tableHeight,
    }));
    t.mock.method(header, "getBoundingClientRect", () => ({
      height: headerHeight,
    }));
    window.document.querySelector("main").replaceChildren(view);
    if (observed) {
      assert.deepEqual(
        observer.observe.mock.calls.map((call) => call.arguments[0]),
        [scroller, table, header],
      );
      observer.callback();
    } else {
      t.mock.timers.tick(0);
    }
    assert.equal(frame.classList.contains("fits"), true);
    assert.equal(frame.classList.contains("sticky-header"), true);
    assert.equal(header.style.getPropertyValue("--header-travel"), "900px");
    assert.equal(header.style.getPropertyValue("--header-height"), "300px");
    assert.equal(header.style.getPropertyValue("--viewport-height"), "900px");

    viewport.clientHeight = 899;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("fits"), true);
    assert.equal(frame.classList.contains("sticky-header"), false);

    viewport.clientHeight = 900;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("sticky-header"), true);

    headerHeight = 301;
    if (observed) observer.callback();
    else window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("sticky-header"), false);

    headerHeight = 300;
    scroller.clientWidth = 998;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("fits"), false);
    assert.equal(frame.classList.contains("sticky-header"), true);

    tableHeight = 320;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(header.style.getPropertyValue("--header-travel"), "20px");

    scroller.clientWidth = 999;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("fits"), true);
    assert.equal(frame.classList.contains("sticky-header"), true);

    headerHeight = 301;
    scroller.dispatchEvent(new window.Event("scroll"));
    rail.dispatchEvent(new window.Event("scroll"));
    assert.equal(frame.classList.contains("sticky-header"), true);

    const style = header.getAttribute("style");
    dispose();
    viewport.clientHeight = 899;
    window.dispatchEvent(new window.Event("scroll"));
    window.dispatchEvent(new window.Event("resize"));
    t.mock.timers.tick(0);
    assert.equal(frame.classList.contains("sticky-header"), true);
    assert.equal(header.getAttribute("style"), style);
    if (observed) assert.equal(observer.disconnect.mock.callCount(), 1);
  });
}

for (const missingFeature of [
  null,
  "CSS API",
  "view-timeline",
  "animation-timeline",
  "animation-range",
]) {
  test(`CSS header pinning ${missingFeature ? `is disabled without ${missingFeature}` : "avoids JavaScript scroll tracking"}`, async (t) => {
    const window = await setup(t);
    t.mock.timers.enable({ apis: ["setTimeout"] });
    Object.defineProperty(window, "CSS", {
      configurable: true,
      value:
        missingFeature === "CSS API"
          ? undefined
          : { supports: (property) => property !== missingFeature },
    });
    const listen = t.mock.method(globalThis, "addEventListener");
    const view = signals(await load(), null);
    const frame = view.querySelector(".scroll-frame");
    const scroller = frame.querySelector(".scroller");
    const table = scroller.firstElementChild;
    const header = table.querySelector("thead");
    const viewport = window.document.documentElement;
    let tableHeight = 1200.75;
    let headerHeight = 300.25;
    Object.defineProperties(scroller, {
      scrollWidth: { value: 1000 },
      clientWidth: { value: 400 },
    });
    Object.defineProperty(viewport, "clientHeight", {
      value: 901,
      writable: true,
    });
    const bounds = t.mock.method(table, "getBoundingClientRect", () => ({
      height: tableHeight,
    }));
    const headerBounds = t.mock.method(header, "getBoundingClientRect", () => ({
      height: headerHeight,
    }));
    window.document.querySelector("main").replaceChildren(view);
    t.mock.timers.tick(0);

    assert.equal(
      frame.classList.contains("scroll-driven-header"),
      missingFeature === null,
    );
    assert.equal(
      frame.classList.contains("sticky-header"),
      missingFeature === null,
    );
    assert.equal(
      listen.mock.calls.some((call) => call.arguments[0] === "scroll"),
      false,
    );
    if (missingFeature === null) {
      assert.equal(header.style.getPropertyValue("--header-travel"), "900.5px");
      assert.equal(
        header.style.getPropertyValue("--header-height"),
        "300.25px",
      );
      assert.equal(header.style.getPropertyValue("--viewport-height"), "901px");
    } else {
      assert.equal(header.getAttribute("style"), null);
      assert.equal(bounds.mock.callCount(), 0);
      assert.equal(headerBounds.mock.callCount(), 0);
    }

    const style = header.getAttribute("style");
    const measurements = bounds.mock.callCount();
    const headerMeasurements = headerBounds.mock.callCount();
    window.dispatchEvent(new window.Event("scroll"));
    assert.equal(header.getAttribute("style"), style);
    assert.equal(bounds.mock.callCount(), measurements);
    assert.equal(headerBounds.mock.callCount(), headerMeasurements);

    viewport.clientHeight = 900;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(frame.classList.contains("sticky-header"), false);

    tableHeight = 600.5;
    headerHeight = 199.25;
    viewport.clientHeight = 600;
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(
      frame.classList.contains("sticky-header"),
      missingFeature === null,
    );
    if (missingFeature === null) {
      assert.equal(
        header.style.getPropertyValue("--header-travel"),
        "401.25px",
      );
      assert.equal(
        header.style.getPropertyValue("--header-height"),
        "199.25px",
      );
      assert.equal(header.style.getPropertyValue("--viewport-height"), "600px");
    } else {
      assert.equal(header.getAttribute("style"), null);
    }

    const resizedStyle = header.getAttribute("style");
    const reads = bounds.mock.callCount();
    dispose();
    window.dispatchEvent(new window.Event("scroll"));
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(header.getAttribute("style"), resizedStyle);
    assert.equal(bounds.mock.callCount(), reads);
  });
}

test("fallback resize listeners and pending updates are removed when the heatmap is replaced", async (t) => {
  const window = await setup(t);
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));

  const scroller = main.querySelector(".scroller");
  const rail = main.querySelector(".scroll-rail");
  Object.defineProperty(scroller, "scrollWidth", {
    value: 1000,
    writable: true,
  });
  t.mock.timers.tick(0);
  assert.equal(rail.firstElementChild.style.width, "1000px");

  driver(window, main).search("jdbc");
  const replacementRail = main.querySelector(".scroll-rail");
  driver(window, main).search("absent");
  assert.equal(main.querySelector(".scroll-frame"), null);

  scroller.scrollWidth = 1500;
  window.dispatchEvent(new window.Event("resize"));
  t.mock.timers.tick(0);
  assert.equal(rail.firstElementChild.style.width, "1000px");
  assert.equal(replacementRail.firstElementChild.style.width, "");
});

test("disposing the signals view cancels pending measurement and resize tracking", async (t) => {
  const window = await setup(t);
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const scroller = main.querySelector(".scroller");
  const rail = main.querySelector(".scroll-rail");
  Object.defineProperty(scroller, "scrollWidth", { value: 1000 });

  dispose();
  main.replaceChildren();
  window.dispatchEvent(new window.Event("resize"));
  t.mock.timers.tick(0);

  assert.equal(rail.firstElementChild.style.width, "");
  dispose();
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
  // The heading says what is being chosen, so the button only shows the
  // choice; what it dropped has to stay in the accessible name.
  assert.doesNotMatch(ui.picker().textContent, /signal/i);
  assert.equal(
    ui.picker().getAttribute("aria-label"),
    "Signal: metric db.duration",
  );
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

  assert.equal(
    window.document.querySelector('nav [aria-current="page"]').textContent,
    "Signal parity",
  );
  const column = main.querySelector("th.col a");
  assert.ok(column);
  const scroller = main.querySelector(".scroller");
  const rail = main.querySelector(".scroll-rail");
  Object.defineProperty(scroller, "scrollWidth", {
    value: 1000,
    writable: true,
  });
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(rail.firstElementChild.style.width, "1000px");

  window.location.hash = column.getAttribute("href");
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.ok(main.querySelector(".target-detail"));
  scroller.scrollWidth = 1500;
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(rail.firstElementChild.style.width, "1000px");
  assert.match(window.document.title, /jdbc/);
  assert.equal(
    window.document.querySelector('nav [aria-current="page"]').textContent,
    "Instrumentations",
  );
  for (const hash of ["#/target", "#/target/"]) {
    window.location.hash = hash;
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    assert.ok(main.querySelector(".picker"));
    assert.equal(main.querySelector(".target-detail"), null);
    assert.equal(
      window.document.querySelector('nav [aria-current="page"]').textContent,
      "Instrumentations",
    );
  }

  window.location.hash = "#/signals/50%";
  window.dispatchEvent(new window.HashChangeEvent("hashchange"));
  assert.ok(main.querySelector("table"));
  assert.doesNotMatch(main.textContent, /Could not render/);
});

test("refinement attributes appear separately from scored requirements", async (t) => {
  const document = report();
  document.targets[0].signals[0].emitted.push("vendor.response");
  document.registry["database-conformance"].metrics["db.duration"].refinements =
    {
      "vendor.db.duration": {
        attributes: { "vendor.response": "required" },
      },
    };
  const window = await setup(t, document);
  const main = window.document.querySelector("main");
  main.replaceChildren(signals(await load(), null));
  const ui = driver(window, main);

  assert.match(
    main.querySelector("details.lede summary").textContent,
    /Rows are the 2 attributes .*, plus 1 more its refinements declare;/,
  );
  const heads = [...main.querySelectorAll("tr.level-head")];
  assert.match(heads.at(-1).textContent, /Refinement attributes \(unscored\)/);
  assert.equal(
    heads.at(-1).querySelector("i").getAttribute("style"),
    "background:var(--refinement)",
  );
  assert.match(main.textContent, /vendor.response/);
  assert.equal(main.querySelectorAll("td.cell-yes").length, 2);
  ui.level("Required + recommended");
  assert.doesNotMatch(main.textContent, /vendor.response|unscored/);
  assert.equal(main.querySelectorAll("td.cell-yes").length, 1);
});
