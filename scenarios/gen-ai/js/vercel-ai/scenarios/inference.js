// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { generateText } = require("ai");
const { provider, request, sampling } = require("./common");
module.exports = async () => {
  await generateText({
    model: provider().chat("gpt-4o-mini"),
    ...request(),
    ...sampling,
  });
};
