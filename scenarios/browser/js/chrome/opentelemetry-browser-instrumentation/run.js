// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Opens one of the pages in `pages/` in headless Chrome. Each page registers
 * one module of @opentelemetry/browser-instrumentation, so a scenario's
 * report holds that module's telemetry and nothing else.
 */

const { runInBrowser } = require("@otel-conformance/browser-runner");

runInBrowser({ page: require.resolve(`./pages/${process.argv[2]}.js`) }).then(
  (seen) => console.log(JSON.stringify(seen)),
  (error) => {
    console.error(error);
    process.exitCode = 1;
  },
);
