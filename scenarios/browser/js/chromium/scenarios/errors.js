// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * Raises the two kinds of error a page can leave unhandled: one thrown from
 * a task, one promise rejected with nothing to catch it.
 */
function raiseErrors() {
  setTimeout(() => {
    throw new TypeError("thrown from a task");
  }, 0);
  Promise.reject(new Error("rejected and not handled"));
}

module.exports = { raiseErrors };
