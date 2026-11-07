// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { attributeUrl, columnName, load } from "../assets/data.js";
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

test("attributes link to the registry that declares them", () => {
  const docs = "https://opentelemetry.io/docs/specs/semconv/registry";
  assert.equal(
    attributeUrl("http.request.method"),
    `${docs}/attributes/http/#http-request-method`,
  );
  assert.equal(
    attributeUrl("user_agent.original"),
    `${docs}/attributes/user-agent/#user-agent-original`,
  );

  const pin = {
    registry_repo: "open-telemetry/semantic-conventions-genai",
    registry_ref: "4a39b6ef",
    registry_dir: "model",
  };
  assert.equal(
    attributeUrl("gen_ai.request.model", pin),
    "https://github.com/open-telemetry/semantic-conventions-genai/tree/4a39b6ef/model/gen-ai",
  );
  assert.equal(attributeUrl("gen_ai.request.model"), null);
  // Standard attributes the GenAI registry also declares are published, so
  // they go to the documentation rather than to that registry's source.
  assert.equal(
    attributeUrl("error.type", pin),
    `${docs}/attributes/error/#error-type`,
  );
});

test("every attribute in the committed report resolves to a link", async () => {
  const document = JSON.parse(
    await readFile(
      new URL("../data/conformance.json", import.meta.url),
      "utf8",
    ),
  );
  for (const [runner, kinds] of Object.entries(document.registry)) {
    for (const declarations of Object.values(kinds)) {
      for (const declaration of Object.values(declarations)) {
        for (const attribute of Object.keys(declaration?.attributes ?? {})) {
          assert.ok(
            attributeUrl(attribute, document.domains[runner]),
            `${attribute} (${runner}) has no registry link`,
          );
        }
      }
    }
  }
});

test("column names shorten the distribution and qualify by backend and side", () => {
  assert.deepEqual(columnName(target(), false), {
    library: "jdbc",
    qualifier: "mariadb",
    distribution: "otel-javaagent",
  });
  const express = target({
    instrumented_library: "express",
    label: "opentelemetry-express",
    backend: null,
    side: "server",
  });
  assert.deepEqual(columnName(express, true), {
    library: "express",
    qualifier: "server",
    distribution: "otel",
  });
  assert.equal(columnName(express, false).qualifier, "");
  assert.equal(
    columnName(target({ label: "otelhttp" }), false).distribution,
    "otelhttp",
  );
});

test("every committed signal has distinct column names within each language", async (t) => {
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
    const sided =
      new Set(signal.rows.map((row) => row.target.side ?? "")).size > 1;
    const columns = signal.rows.map(({ target }) => {
      const name = columnName(target, sided);
      return `${target.language}:${name.library}:${name.qualifier}:${name.distribution}`;
    });
    assert.equal(new Set(columns).size, columns.length, signal.key);
  }
});

test("committed targets round-trip", async (t) => {
  const { ratio } = await import("../assets/data.js");
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
  for (const target of document.targets)
    assert.equal(data.byId.get(target.id), target);
  assert.equal(ratio({ emitted: 0, declared: 0 }), null);
  assert.equal(ratio({ emitted: 1, declared: 2 }), 0.5);
});

test("refinement-only attributes are visible without becoming base requirements", async (t) => {
  const document = report();
  const declaration =
    document.registry["database-conformance"].metrics["db.duration"];
  declaration.refinements = {
    "vendor.db.duration": {
      attributes: { "db.system": "opt_in", "vendor.response": "required" },
    },
  };
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  const signal = (await load()).signals.get("metric:db.duration");
  assert.equal(signal.attributes, declaration.attributes);
  assert.deepEqual(signal.refinementAttributes, new Set(["vendor.response"]));
});

test("runners that differ only in refinements are merged, not conflicting", async (t) => {
  const document = report([target(), target({ id: "other", runner: "other" })]);
  const declaration =
    document.registry["database-conformance"].metrics["db.duration"];
  declaration.refinements = {
    "vendor.db.duration": { attributes: { "vendor.response": "required" } },
  };
  document.registry.other = {
    metrics: {
      "db.duration": {
        attributes: declaration.attributes,
        refinements: {
          "other.db.duration": { attributes: { "other.response": "opt_in" } },
        },
      },
    },
  };
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => document,
  }));
  const signal = (await load()).signals.get("metric:db.duration");
  assert.equal(signal.rows.length, 2);
  assert.deepEqual(
    signal.refinementAttributes,
    new Set(["vendor.response", "other.response"]),
  );
});
