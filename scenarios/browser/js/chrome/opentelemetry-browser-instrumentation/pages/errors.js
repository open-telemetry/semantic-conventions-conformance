// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  ErrorsInstrumentation,
} = require("@opentelemetry/browser-instrumentation/experimental/errors");
const { exposeEvents } = require("../events");
const { raiseErrors } = require("@otel-conformance/chrome-scenarios/errors");

exposeEvents(
  {
    instrumentations: [new ErrorsInstrumentation()],
    events: { "exception:TypeError": 1, "exception:Error": 1 },
  },
  raiseErrors,
);
