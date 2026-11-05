// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { embedMany } = require("ai");
const { provider } = require("./common");
module.exports = async () => {
  await embedMany({
    model: provider().embedding("text-embedding-3-small"),
    values: ["Say this is a test", "And this is another one"],
    dimensions: 256,
  });
};
