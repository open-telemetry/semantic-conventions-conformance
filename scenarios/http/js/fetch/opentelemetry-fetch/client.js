// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { runInBrowser } = require("@otel-conformance/browser-runner");
const { scenarioRequest } = require("@otel-conformance/http-test-client");

runInBrowser({
  page: require.resolve("./browser.js"),
  data: { exchanges: [scenarioRequest()] },
}).then(
  (answered) => {
    for (const line of answered) {
      console.log(line);
    }
  },
  (error) => {
    console.error(error);
    process.exitCode = 1;
  },
);
