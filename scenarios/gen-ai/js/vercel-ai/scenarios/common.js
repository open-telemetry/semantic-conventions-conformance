// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { createOpenAI } = require("@ai-sdk/openai");
const { tool, jsonSchema } = require("ai");

module.exports = {
  provider: () =>
    createOpenAI({
      baseURL: process.env.OPENAI_BASE_URL,
      apiKey: process.env.OPENAI_API_KEY,
    }),
  request: () => ({
    instructions: "You are a helpful assistant.",
    messages: [{ role: "user", content: "Say this is a test" }],
    maxOutputTokens: 100,
    temperature: 0.5,
  }),
  sampling: {
    topP: 0.9,
    frequencyPenalty: 0.1,
    presencePenalty: 0.2,
    stopSequences: ["\n\n"],
    seed: 42,
    providerOptions: { openai: { serviceTier: "default" } },
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
  weatherTool: (execute) =>
    tool({
      description: "Get the current weather in a given location",
      inputSchema: jsonSchema({
        type: "object",
        properties: {
          location: {
            type: "string",
            description: "The city and state, e.g. Boston, MA",
          },
        },
        required: ["location"],
        additionalProperties: false,
      }),
      ...(execute ? { execute } : {}),
    }),
};
