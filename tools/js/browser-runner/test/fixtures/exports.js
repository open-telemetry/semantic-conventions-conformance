// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

const { exportUrl, exposeScenario } = require("../../page");

exposeScenario(async ({ path }) => {
  const answer = await fetch(path);
  const exported = await fetch(exportUrl("traces"), {
    method: "POST",
    headers: { "content-type": "application/x-protobuf" },
    body: new Uint8Array([1, 2, 3]),
  });
  return { answer: await answer.text(), exported: exported.status };
});
