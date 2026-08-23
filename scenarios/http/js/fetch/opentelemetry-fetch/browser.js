// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  FetchInstrumentation,
} = require("@opentelemetry/instrumentation-fetch");
const {
  drive,
  finish,
  onLoad,
  start,
} = require("@otel-conformance/http-browser-test-client/browser");
const { send } = require("@otel-conformance/fetch-scenarios");

const harness = start([
  new FetchInstrumentation({
    ignoreUrls: [/\/__done$/, /\/v1\/traces$/],
  }),
]);
onLoad(async () => {
  let failure;
  try {
    await drive(send);
  } catch (error) {
    failure = error;
  }
  await finish(harness, failure);
});
