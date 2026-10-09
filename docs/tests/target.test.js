// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { load } from "../assets/data.js";
import { split } from "../assets/route.js";
import view, { title } from "../assets/views/target.js";
import signals from "../assets/views/signals.js";
import { report, target } from "./fixtures.js";
import { setup } from "./harness.js";

const coverage = {
  required: { emitted: 1, declared: 1 },
  recommended: { emitted: 0, declared: 1 },
};
function detailed() {
  const document = report([
    target({
      scenario_classes: ["query"],
      signals: [
        {
          type: "metric",
          name: "db.duration",
          emitted: ["db.system", "extra"],
          missing: ["db.namespace"],
          coverage,
        },
        { type: "span", name: "query", emitted: ["db.system"], coverage },
        { type: "event", name: "log", emitted: [], coverage },
        { type: "metric", name: "unknown", emitted: ["custom"] },
      ],
      findings: [
        {
          id: "missing_attribute",
          message: "Extra attribute",
          signal_type: "metric",
          signal_name: "db.duration",
        },
        {
          id: "required_attribute_not_present",
          message: "Expected attribute",
          signal_type: "log",
          signal_name: "log",
        },
        ...Array.from({ length: 4 }, () => ({
          id: "type_mismatch",
          message: "Wrong type",
          signal_type: "metric",
          signal_name: "db.duration",
        })),
        {
          id: "new_rule",
          message: "Unknown violation",
          signal_type: "span",
          // The span's own name, which is not the registry's.
          signal_name: "SELECT",
        },
      ],
      entities: { service: { identity: ["service.name"], description: [] } },
    }),
    // A second instrumentation of jdbc, so the same-library link has a peer.
    target({
      id: "database/java/mariadb/jdbc/other",
      instrumentation_library: "other",
      label: "other",
      path: "scenarios/database/java/mariadb/jdbc/other",
      signals: [{ type: "metric", name: "db.duration", emitted: [] }],
    }),
  ]);
  document.registry["database-conformance"].spans = {
    query: { kind: "client", attributes: { "db.system": "required" } },
  };
  document.registry["database-conformance"].events = {
    log: { attributes: { "db.namespace": "recommended" } },
  };
  document.registry["database-conformance"].entities = {
    service: { description: { "service.version": "recommended" } },
  };
  return document;
}

// The rows of one Needs attention subsection, by its heading.
function attention(page, heading) {
  const group = [
    ...page.querySelectorAll(
      'section[aria-label="Needs attention"] .fix-group',
    ),
  ].find((node) => node.querySelector("h3").firstChild.textContent === heading);
  return group ? [...group.querySelectorAll(".fixes > li")] : [];
}
const lead = (page) => page.querySelector(".verdict-lead").textContent;

test("header, verdict, section order and comparison links", async (t) => {
  const document = detailed();
  await setup(t, document);
  const data = await load();
  const page = view(data, document.targets[0].id);
  const meta = page.querySelector(".meta");
  assert.ok(
    meta.querySelector(
      'a[href="https://github.com/open-telemetry/demo/tree/v1/model"]',
    ),
  );
  assert.ok(
    meta.querySelector(
      `a[href="https://github.com/open-telemetry/semantic-conventions-conformance/tree/main/${document.targets[0].path}"]`,
    ),
  );
  assert.match(meta.textContent, /Scenarios.*query/);
  assert.deepEqual(
    [...page.querySelectorAll(":scope > section[aria-label]")].map((node) =>
      node.getAttribute("aria-label"),
    ),
    ["Coverage", "Needs attention", "Signals", "Resource entities"],
  );
  assert.equal(
    lead(page),
    "2 convention rules broken, 1 absence finding reported.",
  );
  assert.equal(
    page.querySelector(".verdict-sub").textContent,
    "1/1 required and 0/1 recommended attributes emitted across 4 signals. 1 name emitted that the registry doesn't define.",
  );
  assert.equal(page.querySelector(".verdict-mark").textContent, "!");
  assert.match(
    page.querySelector('section[aria-label="Resource entities"]').textContent,
    /service\.version/,
  );
  const same = [...meta.querySelectorAll("a")].find((a) =>
    a.textContent.startsWith("Compare all"),
  );
  const route = split(same.getAttribute("href"));
  assert.equal(route.params.get("lib"), "jdbc");
  assert.equal(
    signals(
      data,
      route.path.slice("/signals/".length),
      route.params,
    ).querySelector('select[aria-label="Library"]').value,
    "jdbc",
  );
  assert.match(title(data, document.targets[0].id), /jdbc.*conformance/);
});

test("a clean run reads as conformant and has nothing to fix", async (t) => {
  const document = report([
    target({
      signals: [
        {
          type: "metric",
          name: "db.duration",
          emitted: ["db.system", "db.namespace"],
          coverage: {
            required: { emitted: 1, declared: 1 },
            recommended: { emitted: 1, declared: 1 },
          },
        },
      ],
      summary: {
        required: { emitted: 1, declared: 1 },
        recommended: { emitted: 1, declared: 1 },
        findings: 0,
      },
    }),
  ]);
  await setup(t, document);
  const page = view(await load(), document.targets[0].id);
  assert.equal(
    lead(page),
    "Meets every required attribute and breaks no rule.",
  );
  assert.equal(page.querySelector(".verdict-mark").textContent, "✓");
  assert.equal(
    page.querySelector('section[aria-label="Needs attention"]'),
    null,
  );
  assert.equal(page.querySelectorAll(".compare").length, 1);
});

for (const id of [
  "required_attribute_not_present",
  "error_type_missing_on_error",
]) {
  test(`${id} fails the verdict even with complete coverage`, async (t) => {
    const document = report([
      target({
        signals: [
          {
            type: "metric",
            name: "db.duration",
            emitted: ["db.system", "db.namespace"],
            coverage: {
              required: { emitted: 1, declared: 1 },
              recommended: { emitted: 1, declared: 1 },
            },
          },
        ],
        summary: {
          required: { emitted: 1, declared: 1 },
          recommended: { emitted: 1, declared: 1 },
          findings: 1,
        },
        findings: [
          {
            id,
            message: "An attribute was missing on another observation.",
            context: {
              attribute_key:
                id === "required_attribute_not_present"
                  ? "db.system"
                  : "error.type",
            },
            signal_type: "metric",
            signal_name: "db.duration",
          },
        ],
      }),
    ]);
    await setup(t, document);
    const page = view(await load(), document.targets[0].id);
    assert.equal(lead(page), "1 absence finding reported.");
    assert.equal(page.querySelector(".verdict-mark").textContent, "!");
    assert.equal(attention(page, "Expected, not emitted").length, 1);
    assert.match(
      page.querySelector(".verdict-sub").textContent,
      /1\/1 required/,
    );
  });
}

test("an absence folded into a recommended row still fails the verdict", async (t) => {
  const document = report([
    target({
      signals: [
        {
          type: "metric",
          name: "db.duration",
          emitted: ["db.system"],
          coverage,
        },
      ],
      findings: [
        {
          id: "recommended_attribute_not_present",
          message: "Recommended attribute 'db.namespace' is not present.",
          context: { attribute_key: "db.namespace" },
          signal_type: "metric",
          signal_name: "db.duration",
        },
      ],
    }),
  ]);
  await setup(t, document);
  const page = view(await load(), document.targets[0].id);
  assert.equal(lead(page), "1 absence finding reported.");
  assert.equal(page.querySelector(".verdict-mark").textContent, "!");
  const [row] = attention(page, "Recommended attributes not emitted");
  assert.equal(row.dataset.findings, "1");
  assert.equal(attention(page, "Expected, not emitted").length, 0);
});

for (const unknown of [false, true]) {
  test(`coverage is unassessed with ${unknown ? "only undeclared" : "no"} signals`, async (t) => {
    const document = report([
      target({
        signals: unknown
          ? [
              {
                type: "metric",
                name: "custom.metric",
                emitted: ["custom.attr"],
                declared: null,
              },
            ]
          : [],
        summary: {
          required: { emitted: 0, declared: 0 },
          recommended: { emitted: 0, declared: 0 },
          findings: 0,
        },
      }),
    ]);
    await setup(t, document);
    const page = view(await load(), document.targets[0].id);
    assert.equal(
      lead(page),
      "No coverage assessed: nothing here matched a registry declaration.",
    );
    assert.equal(page.querySelector(".verdict-mark").textContent, "!");
    assert.equal(page.querySelectorAll(".compare").length, unknown ? 1 : 0);
  });
}

test("a required miss is rolled up at its strictest level", async (t) => {
  const document = report([
    target({
      // The conditional declaration comes first, so letting the first signal
      // decide the level would drop the required miss.
      signals: [
        {
          type: "metric",
          name: "db.connections",
          emitted: [],
          coverage: {
            conditionally_required_conditional: { emitted: 0, declared: 1 },
          },
        },
        {
          type: "metric",
          name: "db.duration",
          emitted: ["db.namespace"],
          coverage: {
            required: { emitted: 0, declared: 1 },
            recommended: { emitted: 1, declared: 1 },
          },
        },
      ],
      summary: {
        required: { emitted: 0, declared: 1 },
        recommended: { emitted: 1, declared: 1 },
        findings: 1,
      },
      findings: [
        {
          id: "required_attribute_not_present",
          message: "Required attribute 'db.system' is not present.",
          context: { attribute_key: "db.system" },
          signal_type: "metric",
          signal_name: "db.duration",
        },
      ],
    }),
  ]);
  document.registry["database-conformance"].metrics[
    "db.connections"
  ].attributes["db.system"] = "conditionally_required_conditional";
  await setup(t, document);
  const page = view(await load(), document.targets[0].id);
  // The absence is the same miss as the required row, so it isn't counted twice.
  assert.equal(lead(page), "1 required attribute not emitted.");
  const [row, ...rest] = attention(page, "Required attributes not emitted");
  assert.equal(rest.length, 0);
  assert.equal(row.querySelector(".what a").textContent, "db.system");
  assert.match(row.querySelector(".what small").textContent, /^Required$/);
  assert.deepEqual(
    [...row.querySelectorAll(".where button")].map((b) => b.textContent),
    ["db.connections", "db.duration"],
  );
  // The absence weaver reported folds into the coverage row, not its own.
  assert.equal(row.dataset.findings, "1");
  assert.equal(attention(page, "Expected, not emitted").length, 0);
});

test("findings are grouped, and where-chips open the signal they name", async (t) => {
  const document = detailed();
  const window = await setup(t, document, `#/target/${document.targets[0].id}`);
  const page = view(await load(), document.targets[0].id);
  window.document.querySelector("main").replaceChildren(page);
  const [mismatch, rule] = attention(page, "Breaks the convention");
  assert.equal(mismatch.dataset.findings, "4");
  assert.match(mismatch.textContent, /Attribute type mismatch/);
  assert.match(mismatch.textContent, /reported 4×/);
  // A span finding carries the span's own name; with one span it still opens.
  assert.equal(rule.querySelector(".where button").textContent, "SELECT");
  assert.equal(rule.querySelector(".where button").dataset.opens, "span:query");
  assert.equal(attention(page, "Expected, not emitted").length, 1);
  assert.equal(attention(page, "Recommended attributes not emitted").length, 1);
  assert.equal(attention(page, "Not in the registry").length, 1);

  const rows = [...page.querySelectorAll("tr[data-signal]")];
  // Two grouped findings beat one; nothing has a required miss to outrank it.
  assert.equal(rows[0].dataset.signal, "metric:db.duration");
  assert.equal(rows[0].querySelector(".count-badge").textContent, "2");
  const toggle = rows[0].querySelector(".row-toggle");
  const detail = rows[0].nextElementSibling;
  assert.equal(detail.hidden, true);
  toggle.click();
  assert.equal(detail.hidden, false);
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  const column = (kind) =>
    [...detail.querySelectorAll(`[data-column="${kind}"] li`)].map(
      (li) => li.textContent,
    );
  assert.deepEqual(column("emitted"), ["db.system"]);
  assert.deepEqual(column("missing"), ["db.namespace"]);
  assert.deepEqual(column("extra"), ["extra"]);
  assert.equal(
    split(detail.querySelector(".compare").getAttribute("href")).path,
    "/signals/metric:db.duration",
  );
  toggle.click();
  assert.equal(detail.hidden, true);

  const unknown = rows.find((row) => row.dataset.signal === "metric:unknown");
  assert.match(unknown.nextElementSibling.textContent, /no declaration/);
  assert.match(unknown.textContent, /n\/a/);

  mismatch
    .querySelector('.where button[data-opens="metric:db.duration"]')
    .click();
  assert.equal(detail.hidden, false);
  assert.equal(window.location.hash, `#/target/${document.targets[0].id}`);
  assert.equal(window.document.activeElement, toggle);
});

test("unknown and empty routes retain picker; multiword search and hotkey route escaped ids", async (t) => {
  const item = target({
    id: "http/java/a space/server?",
    domain: "http",
    language: "java",
    instrumented_library: "armeria",
    side: "server",
  });
  const window = await setup(t, report([item]));
  const data = await load();
  assert.match(
    view(data, "nope").querySelector(".note").textContent,
    /No instrumentation called nope/,
  );
  const page = view(data, null);
  window.document.querySelector("main").replaceChildren(page);
  assert.equal(page.querySelector(".note"), null);
  assert.equal(title(data, null), "instrumentations · conformance");
  window.document.dispatchEvent(
    new window.KeyboardEvent("keydown", { key: "k", metaKey: true }),
  );
  assert.equal(page.querySelector(".palette").hidden, false);
  const input = page.querySelector("input");
  input.value = "java armeria server";
  input.dispatchEvent(new window.Event("input"));
  assert.equal(page.querySelectorAll('[role="option"]').length, 1);
  input.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter" }));
  assert.equal(window.location.hash, "#/target/http/java/a%20space/server%3F");
  assert.equal(split(window.location.hash).path, "/target/" + item.id);
});

test("every committed target accounts for each finding once", async (t) => {
  const document = JSON.parse(
    await readFile(
      new URL("../data/conformance.json", import.meta.url),
      "utf8",
    ),
  );
  await setup(t, document);
  const data = await load();
  for (const item of data.targets) {
    const page = view(data, item.id);
    const counted = [
      ...page.querySelectorAll(
        'section[aria-label="Needs attention"] [data-findings]',
      ),
    ]
      .map((node) => Number(node.dataset.findings))
      .reduce((sum, n) => sum + n, 0);
    assert.equal(counted, item.findings.length, item.id);
    assert.equal(
      page.querySelectorAll(".compare").length,
      item.signals.length,
      item.id,
    );
  }
});
