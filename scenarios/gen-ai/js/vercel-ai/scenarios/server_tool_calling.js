// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText } = require("ai");
const { provider, request } = require("./common");

module.exports = async () => {
  const openai = provider();
  await generateText({
    ...request(),
    model: openai.responses("gpt-4o-mini"),
    messages: [{ role: "user", content: "What is OpenTelemetry?" }],
    tools: { web_search: openai.tools.webSearch({}) },
  });
};
