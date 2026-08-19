// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The undici client scenario, measured through explicit instrumentation.
 *
 * One instrumentation and no HTTP one beside it, unlike the Express server:
 * undici does not go through Node's `http` module, so what it sends is only
 * ever seen by `@opentelemetry/instrumentation-undici`.
 */

const {
  UndiciInstrumentation,
} = require("@opentelemetry/instrumentation-undici");
const { runScenario } = require("@otel-conformance/scenario-sdk");

runScenario({ instrumentations: [new UndiciInstrumentation()] }, () =>
  // Required inside the workload so undici is loaded after the
  // instrumentation that patches it has been registered.
  require("@otel-conformance/undici-scenarios").drivePackagedContract(),
);
