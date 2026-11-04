// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText } = require("ai");
const { provider, request } = require("./common");
module.exports = async () => {
  const model = provider().chat("gpt-4o-mini");
  await generateText({
    ...request(),
    model,
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: "What is in this image?" },
          {
            type: "file",
            mediaType: "image/png",
            data: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
          },
        ],
      },
    ],
  });
  await generateText({
    ...request(),
    model: provider().chat("gpt-4o-audio-preview"),
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: "Repeat what you hear." },
          { type: "file", data: "bW9jaw==", mediaType: "audio/wav" },
        ],
      },
    ],
  });
};
