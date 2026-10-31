// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client, schema } = require("./common");
module.exports = async () => {
  await client().chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "What is the weather in Seattle?" },
    ],
    response_format: {
      type: "json_schema",
      json_schema: { name: "forecast", strict: true, schema },
    },
    max_tokens: 100,
    temperature: 0.5,
  });
};
