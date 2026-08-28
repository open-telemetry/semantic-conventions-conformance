// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { HttpInstrumentation } = require("@opentelemetry/instrumentation-http");
const { runScenario } = require("@otel-conformance/scenario-sdk");

runScenario(
  {
    instrumentations: [
      new HttpInstrumentation({ disableOutgoingRequestInstrumentation: true }),
    ],
  },
  () => require("@otel-conformance/node-http-scenarios/server").serve(),
);
