// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { attributeUrl, distinguish, load } from "../assets/data.js";
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

test("one library shared by two languages needs no distribution", () => {
  const targets = [
    target({
      id: "http/go/net-http/otelhttp",
      language: "go",
      backend: null,
      instrumented_library: "net/http",
      label: "otelhttp",
    }),
    target({
      id: "http/ruby/net-http/instrumentation",
      language: "ruby",
      backend: null,
      instrumented_library: "net/http",
      label: "opentelemetry-instrumentation-net_http",
    }),
  ];
  const labels = [...distinguish(targets).values()];
  assert.deepEqual(
    labels.map((label) => label.secondary),
    [null, null],
  );
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
