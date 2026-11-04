// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { client } = require("./common");
module.exports = async () => {
  await client().embeddings.create({
    model: "text-embedding-3-small",
    input: ["Say this is a test", "And this is another one"],
    encoding_format: "float",
    dimensions: 256,
  });
};
