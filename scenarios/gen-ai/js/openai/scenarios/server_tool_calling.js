// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client } = require("./common");

module.exports = async () => {
  await client().responses.create({
    model: "gpt-4o-mini",
    instructions: "You are a helpful assistant.",
    input: "What is OpenTelemetry?",
    tools: [{ type: "web_search" }],
    max_output_tokens: 100,
    temperature: 0.5,
  });
};
