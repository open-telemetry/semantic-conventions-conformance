// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/** Writes one message at each console level an application commonly uses. */
function writeToConsole() {
  console.log("a log message");
  console.warn("a warning");
  console.error("an error message");
}

module.exports = { writeToConsole };
