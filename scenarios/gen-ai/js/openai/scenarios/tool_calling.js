// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client, tool } = require("./common");
module.exports = async () => {
  const sdk = client();
  const messages = [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "What's the weather in Seattle today?" },
  ];
  const options = {
    model: "gpt-4o-mini",
    tools: [tool],
    max_tokens: 100,
    temperature: 0.5,
  };
  const first = await sdk.chat.completions.create({
    ...options,
    messages,
    tool_choice: "auto",
  });
  const assistant = first.choices[0].message;
  messages.push(assistant);
  for (const call of assistant.tool_calls ?? []) {
    const { location } = JSON.parse(call.function.arguments);
    messages.push({
      role: "tool",
      content: `70 degrees and sunny in ${location}`,
      tool_call_id: call.id,
    });
  }
  await sdk.chat.completions.create({ ...options, messages });
};
