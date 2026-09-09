// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { distinguish, load } from "../assets/data.js";
import { report, target } from "./fixtures.js";

test("load fetches the report and rejects unsupported schemas and HTTP failures", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.equal(url, "data/conformance.json");
    return { ok: true, json: async () => report() };
  });
  const data = await load();
  assert.equal(data.signals.get("metric:db.duration").rows.length, 1);
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ schema_version: 999 }),
  });
  await assert.rejects(load(), /schema_version 999/);
  globalThis.fetch = async () => ({ ok: false, status: 404 });
  await assert.rejects(load(), /404/);
});

test("compatible declarations from different runners can be compared", async (t) => {
  const document = report([target(), target({ id: "other", runner: "other" })]);
  document.registry.other = {
    metrics: {
      "db.duration": {
        attributes: {
          "db.namespace": "recommended",
          "db.system": "required",
        },
      },
    },
  };
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  assert.equal((await load()).signals.get("metric:db.duration").rows.length, 2);
});

for (const declaration of [
  { attributes: { "db.system": "recommended", "db.namespace": "recommended" } },
  { attributes: { "db.other": "required" } },
  {
    attributes: { "db.system": "required", "db.namespace": "recommended" },
    kind: "client",
  },
  null,
]) {
  test(`rejects incompatible declarations: ${JSON.stringify(declaration)}`, async (t) => {
    const document = report([
      target(),
      target({ id: "other", runner: "other" }),
    ]);
    document.registry.other = { metrics: { "db.duration": declaration } };
    t.mock.method(globalThis, "fetch", async () => ({
      ok: true,
      json: async () => document,
    }));
    await assert.rejects(
      load(),
      /Conflicting declarations.*database-conformance and other/,
    );
    document.targets.reverse();
    await assert.rejects(
      load(),
      /Conflicting declarations.*other and database-conformance/,
    );
  });
}

test("span and metric names do not collide, and unknown declarations stay unknown", async (t) => {
  const document = report([
    target({
      signals: [
        { type: "span", name: "shared", emitted: [] },
        { type: "metric", name: "shared", emitted: [] },
      ],
    }),
  ]);
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  const data = await load();
  assert.equal(data.signals.size, 2);
  assert.equal(data.signals.get("span:shared").attributes, null);
});

test("database labels distinguish both backend and instrumentation", () => {
  const targets = ["mariadb", "postgresql"].flatMap((backend) =>
    ["opentelemetry-javaagent", "opentelemetry-library"].map((label) =>
      target({
        id: `database/java/${backend}/jdbc/${label}`,
        backend,
        label,
      }),
    ),
  );
  const labels = [...distinguish(targets).values()];
  assert.equal(new Set(labels.map((label) => label.secondary)).size, 4);
  assert.equal(new Set(labels.map((label) => label.full)).size, 4);
  assert.equal(labels[0].secondary, "mariadb · opentelemetry-javaagent");
});

test("competing instrumentations and HTTP sides remain distinguishable", () => {
  const targets = ["client", "server"].flatMap((side) =>
    ["native", "instrumented"].map((label) =>
      target({
        id: `${side}/${label}`,
        backend: null,
        side,
        label,
      }),
    ),
  );
  const labels = [...distinguish(targets).values()];
  assert.equal(new Set(labels.map((label) => label.secondary)).size, 4);
  assert.equal(distinguish([targets[0]]).get(targets[0].id).secondary, null);
});

test("every committed signal has distinct column labels within each language", async (t) => {
  const document = JSON.parse(
    await readFile(
      new URL("../data/conformance.json", import.meta.url),
      "utf8",
    ),
  );
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  const data = await load();
  for (const signal of data.signals.values()) {
    const labels = distinguish(signal.rows.map((row) => row.target));
    const columns = signal.rows.map(({ target }) => {
      const label = labels.get(target.id);
      return `${target.language}:${label.primary}:${label.secondary}`;
    });
    assert.equal(new Set(columns).size, columns.length, signal.key);
  }
});
