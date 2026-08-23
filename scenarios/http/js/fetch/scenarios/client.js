// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

async function send(method, url, body) {
  const response = await fetch(url, {
    method,
    body,
    headers: body === null ? {} : { "content-type": "application/json" },
  });
  return { status: response.status, body: await response.text() };
}

module.exports = { send };
