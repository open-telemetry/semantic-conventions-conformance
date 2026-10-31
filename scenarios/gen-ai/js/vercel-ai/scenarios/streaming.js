// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { streamText } = require("ai");
const { provider, request, sampling } = require("./common");
module.exports = async () => {
  const result = streamText({
    model: provider().chat("gpt-4o-mini"),
    ...request(),
    ...sampling,
  });
  await result.consumeStream({
    onError: (error) => {
      throw error;
    },
  });
};
