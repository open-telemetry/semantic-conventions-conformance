// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  FetchInstrumentation,
} = require("@opentelemetry/instrumentation-fetch");
const {
  BRIDGE_PATH,
  exposeScenario,
} = require("@otel-conformance/browser-runner/page");
const { runWithTracing } = require("@otel-conformance/browser-runner/tracing");
const { drive } = require("@otel-conformance/fetch-scenarios");

exposeScenario(({ exchanges }) =>
  runWithTracing({
    instrumentations: [
      new FetchInstrumentation({ ignoreUrls: [new RegExp(`${BRIDGE_PATH}/`)] }),
    ],
    expectedSpans: exchanges.filter((exchange) => !exchange.readiness).length,
    workload: () => drive(location.origin, exchanges),
  }),
);
