// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText } = require("ai");
const { provider, request, weatherTool } = require("./common");
module.exports = async () => {
  const messages = [
    { role: "user", content: "What's the weather in Seattle today?" },
  ];
  const options = {
    ...request(),
    model: provider().chat("gpt-4o-mini"),
    tools: { get_current_weather: weatherTool() },
  };
  const first = await generateText({ ...options, messages });
  messages.push(...first.response.messages);
  messages.push({
    role: "tool",
    content: first.toolCalls.map((call) => ({
      type: "tool-result",
      toolCallId: call.toolCallId,
      toolName: call.toolName,
      output: {
        type: "text",
        value: `70 degrees and sunny in ${call.input.location}`,
      },
    })),
  });
  await generateText({ ...options, messages });
};
