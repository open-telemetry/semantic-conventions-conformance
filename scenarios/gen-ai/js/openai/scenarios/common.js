// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const OpenAI = require("openai");

module.exports = {
  client: () => new OpenAI(),
  messages: () => [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Say this is a test" },
  ],
  sampling: {
    max_tokens: 100,
    temperature: 0.5,
    top_p: 0.9,
    frequency_penalty: 0.1,
    presence_penalty: 0.2,
    stop: ["\n\n"],
    seed: 42,
    service_tier: "default",
  },
  schema: {
    type: "object",
    properties: {
      location: { type: "string" },
      temperature: { type: "integer" },
      conditions: { enum: ["sunny", "cloudy", "rainy"] },
    },
    required: ["location", "temperature", "conditions"],
    additionalProperties: false,
  },
  tool: {
    type: "function",
    function: {
      name: "get_current_weather",
      description: "Get the current weather in a given location",
      parameters: {
        type: "object",
        properties: {
          location: {
            type: "string",
            description: "The city and state, e.g. Boston, MA",
          },
        },
        required: ["location"],
        additionalProperties: false,
      },
    },
  },
};
