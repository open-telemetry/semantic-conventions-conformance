// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { runScenario } = require("@otel-conformance/scenario-sdk");

module.exports = (workload) =>
  runScenario({}, async () => {
    const { registerTelemetry } = require("ai");
    const { OpenTelemetry } = require("@ai-sdk/otel");
    registerTelemetry(new OpenTelemetry());
    await workload();
  });
