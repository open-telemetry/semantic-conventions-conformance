// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

async function forwardTraces(exportPayload, payload, complete) {
  try {
    await exportPayload(payload);
  } catch (error) {
    complete({
      ok: false,
      error: `failed to forward OTLP traces: ${error instanceof Error ? (error.stack ?? error.message) : String(error)}`,
    });
    throw error;
  }
  return payload.length;
}

module.exports = { forwardTraces };
