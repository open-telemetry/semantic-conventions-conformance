// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const path = require("node:path");

const { runBrowserScenario } = require("@otel-conformance/browser-runner");
const { scenarioRequest } = require("@otel-conformance/http-test-client");

runBrowserScenario({
  entrypoint: path.join(__dirname, "browser.js"),
  exchanges: [scenarioRequest()],
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
