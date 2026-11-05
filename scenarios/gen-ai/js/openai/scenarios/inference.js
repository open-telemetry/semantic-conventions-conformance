// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client, messages, sampling } = require("./common");
module.exports = async () => {
  await client().chat.completions.create({
    model: "gpt-4o-mini",
    messages: messages(),
    ...sampling,
  });
};
