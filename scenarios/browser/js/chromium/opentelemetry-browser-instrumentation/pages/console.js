// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  ConsoleInstrumentation,
} = require("@opentelemetry/browser-instrumentation/experimental/console");
const { exposeScenario } = require("@otel-conformance/browser-launcher/page");
const {
  writeToConsole,
} = require("@otel-conformance/chromium-scenarios/console");

exposeScenario(
  {
    instrumentations: [new ConsoleInstrumentation()],
    events: { "browser.console": 3 },
  },
  writeToConsole,
);
