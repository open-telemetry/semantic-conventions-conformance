// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client, messages, sampling } = require("./common");
module.exports = async () => {
  const stream = await client().chat.completions.create({
    model: "gpt-4o-mini",
    messages: messages(),
    ...sampling,
    stream: true,
    stream_options: { include_usage: true },
  });
  for await (const chunk of stream) {
    void chunk;
  }
};
