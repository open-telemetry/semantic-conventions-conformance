// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText, Output, jsonSchema } = require("ai");
const { provider, request, schema } = require("./common");
module.exports = async () => {
  await generateText({
    ...request(),
    model: provider().chat("gpt-4o-mini"),
    messages: [{ role: "user", content: "What is the weather in Seattle?" }],
    output: Output.object({ name: "forecast", schema: jsonSchema(schema) }),
  });
};
