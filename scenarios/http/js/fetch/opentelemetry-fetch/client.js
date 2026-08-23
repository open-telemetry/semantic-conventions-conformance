// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  runBrowserScenario,
} = require("@otel-conformance/http-browser-test-client");

runBrowserScenario({
  entry: require.resolve("./browser.js"),
  title: "Fetch HTTP conformance",
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
