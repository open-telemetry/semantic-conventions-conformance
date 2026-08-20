// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The Express server scenario, measured through explicit instrumentation.
 *
 * `@opentelemetry/instrumentation-express` produces the route and the spans
 * around Express's own middleware, but not the server span they hang from —
 * that comes from `@opentelemetry/instrumentation-http`, which is why both are
 * registered. The package is named for the one being measured.
 */

const {
  ExpressInstrumentation,
} = require("@opentelemetry/instrumentation-express");
const { HttpInstrumentation } = require("@opentelemetry/instrumentation-http");
const { runScenario } = require("@otel-conformance/scenario-sdk");

runScenario(
  {
    instrumentations: [new HttpInstrumentation(), new ExpressInstrumentation()],
  },
  // Required here rather than at the top of the file: Express is patched as it
  // is required, so requiring it before the instrumentations are registered
  // would measure nothing.
  () => require("@otel-conformance/express-scenarios").serve(),
);
