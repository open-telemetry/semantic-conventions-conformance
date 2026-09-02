// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The HTTP conformance exchanges a Node scenario answers or sends.
 *
 * One entry point for both halves of the domain: `contract` decodes runner
 * JSON, `respond` answers concrete requests for any framework, and `drive`
 * sends the runner-selected request with the library under test.
 *
 */

const contract = require("./contract");
const clientWorkload = require("./client-workload");
const serverWorkload = require("./server-workload");

module.exports = {
  ...contract,
  ...clientWorkload,
  ...serverWorkload,
};
