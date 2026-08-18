// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/**
 * The HTTP conformance exchanges a Node scenario answers or sends.
 *
 * One entry point for both halves of the domain: `contract` reads the shared
 * file, `respond` answers concrete requests for any framework, and `drive`
 * sends the measured requests with the library under test.
 *
 * Nothing here has a dependency of its own, so installing it next to a
 * scenario drags nothing into a run.
 */

const contract = require("./contract");
const clientWorkload = require("./client-workload");
const serverWorkload = require("./server-workload");
const { ContractError } = require("./contract-error");

module.exports = {
  ContractError,
  ...contract,
  ...clientWorkload,
  ...serverWorkload,
};
