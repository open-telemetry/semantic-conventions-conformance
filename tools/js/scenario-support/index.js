// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * What the runner told a scenario, and how a long-running one learns that the
 * runner is finished with it.
 *
 * No OpenTelemetry dependency at all, which is the point: a scenario measuring
 * an auto-instrumentation runtime must load only what that runtime brings, so
 * what *every* scenario needs cannot live beside the SDK.
 */

/** The value of `name`, or a failure naming what was missing. */
function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`required environment variable is missing: ${name}`);
  }
  return value;
}

/**
 * Resolves when standard input closes, which is how the driver says stop.
 *
 * A closed pipe rather than a signal: it means the same thing on every
 * platform, and resolving is what gives an SDK the chance to flush, so a
 * scenario that exits any other way reports less than it produced. The
 * protocol is the same in every domain.
 */
function waitForEof() {
  return new Promise((resolve) => {
    const done = () => {
      // Reading is what keeps the process alive once the workload is idle, so
      // stop reading as soon as the driver has said stop.
      process.stdin.pause();
      resolve();
    };
    // Nothing arrives on standard input; only its close is the signal. `close`
    // as well as `end`, because a standard input that was never a pipe — a
    // scenario started by hand — closes without ever ending. A pipe fires both,
    // which is harmless: a promise settles once, and pausing twice is pausing.
    process.stdin.on("end", done);
    process.stdin.on("close", done);
    process.stdin.resume();
  });
}

module.exports = { requireEnv, waitForEof };
