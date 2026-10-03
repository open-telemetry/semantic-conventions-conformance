// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/** Paints text, so first contentful paint can follow time to first byte. */
function paint() {
  const heading = document.createElement("h1");
  heading.textContent = "Browser conformance";
  document.body.append(heading);
}

module.exports = { paint };
