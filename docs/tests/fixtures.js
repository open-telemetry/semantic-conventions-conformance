// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

/**
 * @param {object} [overrides] target fields to replace
 * @returns {import('../assets/data.js').Target} a measured database target
 */
export function target(overrides = {}) {
  return {
    id: "database/java/mariadb/jdbc/opentelemetry-javaagent",
    path: "scenarios/database/java/mariadb/jdbc/opentelemetry-javaagent",
    domain: "database",
    language: "java",
    runner: "database-conformance",
    instrumented_library: "jdbc",
    instrumentation_library:
      "io.opentelemetry.javaagent:opentelemetry-javaagent",
    label: "opentelemetry-javaagent",
    side: null,
    backend: "mariadb",
    signals: [{ type: "metric", name: "db.duration", emitted: ["db.system"] }],
    ...overrides,
  };
}

/**
 * @param {import('../assets/data.js').Target[]} [targets] measured targets
 * @returns {import('../assets/data.js').Report} a report with two declarations
 */
export function report(targets = [target()]) {
  return {
    schema_version: 1,
    domains: {
      "database-conformance": {
        registry_repo: "open-telemetry/demo",
        registry_ref: "v1",
        registry_dir: "model",
      },
    },
    registry: {
      "database-conformance": {
        metrics: {
          "db.duration": {
            attributes: {
              "db.system": "required",
              "db.namespace": "recommended",
            },
          },
          "db.connections": { attributes: { "db.system": "required" } },
        },
      },
    },
    targets,
  };
}
