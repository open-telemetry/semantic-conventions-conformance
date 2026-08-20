// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Sends the shared HTTP exchanges with undici until they are all answered.
 *
 * The mock server the runner started answers the same contract, so what the
 * scenario adds is the sending: the requests go through `undici.request`,
 * which reports every status rather than throwing on 4xx and 5xx, since the
 * contract's failing statuses are traffic to be measured like any other.
 */

const undici = require("undici");
const {
  CONTENT_TYPE,
  USER_AGENT,
  drive,
} = require("@otel-conformance/http-test-client");
const { requireEnv } = require("@otel-conformance/scenario-support");

async function send(method, url, body) {
  const response = await undici.request(url, {
    method,
    body,
    headers: {
      "user-agent": USER_AGENT,
      // Only when there is one to describe, so a GET does not announce a
      // content type for a body it never sent.
      ...(body === null ? {} : { "content-type": CONTENT_TYPE }),
    },
  });
  // Read to the end even where the body is not needed: an unread body holds
  // the connection, and the process would not exit.
  return { status: response.statusCode, body: await response.body.text() };
}

async function drivePackagedContract() {
  try {
    await drive(requireEnv("MOCK_SERVER_URL"), send);
  } finally {
    // undici keeps its pool open for reuse, which outlives the traffic this
    // scenario has to send.
    await undici.getGlobalDispatcher().close();
  }
}

module.exports = { drivePackagedContract, send };
