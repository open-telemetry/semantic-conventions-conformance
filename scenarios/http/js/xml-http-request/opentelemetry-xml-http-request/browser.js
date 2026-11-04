// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  XMLHttpRequestInstrumentation,
} = require("@opentelemetry/instrumentation-xml-http-request");
const {
  BRIDGE_PATH,
  exposeScenario,
} = require("@otel-conformance/browser-runner/page");
const { runWithTracing } = require("@otel-conformance/browser-runner/tracing");
const { drive } = require("@otel-conformance/xml-http-request-scenarios");

exposeScenario(({ exchanges }) =>
  runWithTracing({
    instrumentations: [
      new XMLHttpRequestInstrumentation({
        ignoreUrls: [new RegExp(`${BRIDGE_PATH}/`)],
      }),
    ],
    expectedSpans: exchanges.filter((exchange) => !exchange.readiness).length,
    workload: () => drive(location.origin, exchanges),
  }),
);
