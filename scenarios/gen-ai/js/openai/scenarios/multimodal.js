// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client } = require("./common");
module.exports = async () => {
  const sdk = client();
  await sdk.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      {
        role: "user",
        content: [
          { type: "text", text: "What is in this image?" },
          {
            type: "image_url",
            image_url: {
              url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            },
          },
        ],
      },
    ],
    max_tokens: 100,
    temperature: 0.5,
  });
  await sdk.chat.completions.create({
    model: "gpt-4o-audio-preview",
    modalities: ["text", "audio"],
    audio: { voice: "alloy", format: "wav" },
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      {
        role: "user",
        content: [
          { type: "text", text: "Repeat what you hear." },
          {
            type: "input_audio",
            input_audio: { data: "bW9jaw==", format: "wav" },
          },
        ],
      },
    ],
    max_tokens: 100,
    temperature: 0.5,
  });
};
