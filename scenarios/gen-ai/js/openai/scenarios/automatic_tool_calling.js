// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client, tool } = require("./common");
module.exports = async () => {
  await client()
    .chat.completions.runTools({
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "What's the weather in Seattle today?" },
      ],
      tools: [
        {
          ...tool,
          function: {
            ...tool.function,
            parse: JSON.parse,
            function: async ({ location }) =>
              `70 degrees and sunny in ${location}`,
          },
        },
      ],
      max_tokens: 100,
      temperature: 0.5,
    })
    .finalChatCompletion();
};
