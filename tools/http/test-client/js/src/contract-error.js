// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

"use strict";

/** A server answered something the contract does not describe. */
class ContractError extends Error {
  constructor(message, options) {
    super(message, options);
    this.name = "ContractError";
  }
}

module.exports = { ContractError };
