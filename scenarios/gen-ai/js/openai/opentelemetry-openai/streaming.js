// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const {
  OpenAIInstrumentation,
} = require("@opentelemetry/instrumentation-openai");
const { runScenario } = require("@otel-conformance/scenario-sdk");

runScenario({ instrumentations: [new OpenAIInstrumentation()] }, () =>
  require("@otel-conformance/openai-scenarios/streaming")(),
);
