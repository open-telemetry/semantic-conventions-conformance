// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText, isStepCount } = require("ai");
const { provider, request, weatherTool } = require("./common");
module.exports = async () => {
  await generateText({
    ...request(),
    model: provider().chat("gpt-4o-mini"),
    messages: [
      { role: "user", content: "What's the weather in Seattle today?" },
    ],
    tools: {
      get_current_weather: weatherTool(
        async ({ location }) => `70 degrees and sunny in ${location}`,
      ),
    },
    stopWhen: isStepCount(2),
  });
};
