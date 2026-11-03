// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  WebVitalsInstrumentation,
} = require("@opentelemetry/browser-instrumentation/experimental/web-vitals");
const { exposeScenario } = require("@otel-conformance/browser-launcher/page");
const { paint } = require("@otel-conformance/chromium-scenarios/web-vitals");

exposeScenario(
  {
    instrumentations: [new WebVitalsInstrumentation()],
    events: { "browser.web_vital": 1 },
  },
  paint,
);
