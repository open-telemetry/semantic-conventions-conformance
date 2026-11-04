// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const path = require("node:path");
const test = require("node:test");
const { respond } = require("@otel-conformance/http-test-client");
const {
  assertSelectedHttpClientSpan,
} = require("@otel-conformance/browser-runner/testing");

test("measures only the selected browser XMLHttpRequest request", () =>
  assertSelectedHttpClientSpan(path.resolve(__dirname, ".."), respond));
