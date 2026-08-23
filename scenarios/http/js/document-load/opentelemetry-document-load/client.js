// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  runBrowserScenario,
} = require("@otel-conformance/http-browser-test-client");
const scenario = require("@otel-conformance/document-load-scenarios");

runBrowserScenario({
  entry: require.resolve("./browser.js"),
  ...scenario,
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
