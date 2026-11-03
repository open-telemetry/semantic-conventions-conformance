// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  ErrorsInstrumentation,
} = require("@opentelemetry/browser-instrumentation/experimental/errors");
const { exposeEvents } = require("../events");
const { raiseErrors } = require("@otel-conformance/chromium-scenarios/errors");

exposeEvents(
  { instrumentations: [new ErrorsInstrumentation()], events: { exception: 2 } },
  raiseErrors,
);
