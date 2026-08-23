// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  DocumentLoadInstrumentation,
} = require("@opentelemetry/instrumentation-document-load");
const {
  finish,
  onLoad,
  start,
} = require("@otel-conformance/http-browser-test-client/browser");

const harness = start([new DocumentLoadInstrumentation()]);
onLoad(async () => {
  await finish(harness);
});
